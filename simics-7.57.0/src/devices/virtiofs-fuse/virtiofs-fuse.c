/*
  virtiofs-fuse.c

  © 2023 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/eventfd.h>
#include <sys/select.h>
#include <sys/stat.h>

#include <simics/device-api.h>
#include <simics/base/log.h>
#include "simics/base/attr-value.h"
#include "simics/base/conf-object.h"
#include "simics/util/alloc.h"
#include "simics/simulator/paths.h"

#include "virtiofs-fuse-interface.h"

#define WAIT_FOR_DAEMON_TIMEOUT_S 10
#define MAX_FUSE_PAYLOAD_LEN UINT32_MAX

#define FUSE_FORGET_OPCODE 2

typedef struct fuse_out_header {
        uint32_t len;
        int32_t error;
        uint64_t unique;
} fuse_out_header_t;

typedef struct fuse_in_header {
        uint32_t len;
        uint32_t opcode;
        uint64_t unique;
        uint64_t nodeid;
        uint32_t uid;
        uint32_t gid;
        uint32_t pid;
        uint32_t padding;
} fuse_in_header_t;

typedef struct {
        conf_object_t obj;
        pid_t daemon_pid;
        int sfd;
        char *share;
        char *daemon_log_file;
        bool always_cache;
        bool connection_established;
} fuse_handler_device_t;

static conf_object_t *
alloc_object(conf_class_t *cls)
{
        fuse_handler_device_t *fuse = MM_ZALLOC(1, fuse_handler_device_t);
        fuse->daemon_pid = -1;
        return &fuse->obj;
}

static void
dealloc_object(conf_object_t *obj)
{
        fuse_handler_device_t *fuse = (fuse_handler_device_t *)obj;
        if (fuse->share != NULL) {
                MM_FREE(fuse->share);
        }
        if (fuse->daemon_log_file != NULL) {
                MM_FREE(fuse->daemon_log_file);
        }
        MM_FREE(fuse);
}

static void
unset_connection(fuse_handler_device_t *fuse)
{
        close(fuse->sfd);
        if (fuse->daemon_pid != -1) {
                kill(fuse->daemon_pid, SIGTERM);
        }
        fuse->sfd = -1;
        fuse->daemon_pid = -1;
        fuse->connection_established = false;
}

static void
deinit(conf_object_t *obj)
{
        fuse_handler_device_t *fuse = (fuse_handler_device_t *)obj;
        unset_connection(fuse);
}

static int
connect_to_daemon(conf_object_t *obj, char *socket_path)
{
        fuse_handler_device_t *fuse = (fuse_handler_device_t *)obj;

        struct sockaddr_un addr = { 0 };

        if (strnlen(socket_path, sizeof(addr.sun_path))
            >= sizeof(addr.sun_path)) {
                SIM_LOG_ERROR(
                        obj, 0,
                        "Socket path is too long. Must not be longer than %lu characters",
                        sizeof(addr.sun_path) - 1);
                return -1;
        }

        fuse->sfd = socket(AF_UNIX, SOCK_STREAM, 0);
        if (fuse->sfd == -1) {
                SIM_LOG_ERROR(obj, 0, "Could not create socket. Error: %s",
                              strerror(errno));
                return -1;
        }

        addr.sun_family = AF_UNIX;
        strcpy(addr.sun_path, socket_path);

        if (connect(fuse->sfd, (struct sockaddr *)&addr,
                    sizeof(struct sockaddr_un))
            == -1) {
                SIM_LOG_ERROR(
                        obj, 0,
                        "Could not connect to the fuse daemon's unix domain socket. Error: %s",
                        strerror(errno));
                unset_connection(fuse);
                return -1;
        } else {
                fuse->connection_established = true;
                return 0;
        }
}

static int
initiate_daemon_connection(conf_object_t *obj)
{
        fuse_handler_device_t *fuse = (fuse_handler_device_t *)obj;
        const char *xdg_runtime_dir = getenv("XDG_RUNTIME_DIR");

        if (xdg_runtime_dir == NULL) {
                SIM_LOG_INFO(
                        2, obj, 0,
                        "Using /tmp to store daemon socket since XDG_RUNTIME_DIR is not set by host OS dependencies");
        }

        char socket_path[(xdg_runtime_dir != NULL ? strlen(xdg_runtime_dir)
                                                  : strlen("/tmp"))
                         + 40];
        snprintf(socket_path, sizeof(socket_path), "%s/virtiofs-%ld.sock",
                 xdg_runtime_dir ? xdg_runtime_dir : "/tmp",
                 (long int)time(NULL));

        char *daemon_bin =
                SIM_lookup_file("%simics%/linux64/bin/virtiofs-daemon");
        if (daemon_bin == NULL) {
                SIM_LOG_ERROR(obj, 0,
                              "Could not find virtiofs-daemon executable");
                return -1;
        }

        int efd = eventfd(0, 0);
        char efd_str[20];
        if (efd == -1) {
                SIM_LOG_ERROR(
                        obj, 0,
                        "Could not create file descriptor for event notification. Error: %s",
                        strerror(errno));
                return -1;
        }
        snprintf(efd_str, sizeof(efd_str), "%d", efd);

        fuse->daemon_pid = fork();
        if (fuse->daemon_pid == -1) {
                MM_FREE(daemon_bin);
                SIM_LOG_ERROR(obj, 0,
                              "Could not fork process for daemon. Error: %s",
                              strerror(errno));
                return -1;
        } else if (fuse->daemon_pid == 0) {
                // In this code block, we are the spawned child process from the
                // fork. Here we call execl() to replace the process image of
                // the child process, which after fork is called, is a duplicate
                // of the simics (parent) process. The new process image will be
                // a FUSE daemon process. If the call to execl for some reason
                // fails, the child process should exit, otherwise a duplicate
                // simics process will be running along the parent simics
                // process
                int ret;
                if (fuse->daemon_log_file != NULL) {
                        ret = execl(daemon_bin, daemon_bin, fuse->share,
                                    socket_path, "--cache",
                                    fuse->always_cache ? "always" : "normal",
                                    "--debug", "--debug-fuse", "--nostdout",
                                    "--logfile", fuse->daemon_log_file,
                                    "--eventfd", efd_str, (char *)NULL);
                } else {
                        ret = execl(daemon_bin, daemon_bin, fuse->share,
                                    socket_path, "--cache",
                                    fuse->always_cache ? "always" : "normal",
                                    "--nostdout", "--eventfd", efd_str,
                                    (char *)NULL);
                }

                MM_FREE(daemon_bin);
                if (ret == -1) {
                        SIM_LOG_ERROR(
                                obj, 0,
                                "Could not start the FUSE daemon process. Error: %s",
                                strerror(errno));
                        exit(-1);  // This exits the forked child process, not
                                   // the main simics process
                }
                return -1;  // Unreachable
        } else {
                MM_FREE(daemon_bin);

                fd_set readfds;
                struct timeval timeout;

                timeout.tv_sec = WAIT_FOR_DAEMON_TIMEOUT_S;
                timeout.tv_usec = 0;
                FD_ZERO(&readfds);
                FD_SET(efd, &readfds);
                int ret = select(efd + 1, &readfds, NULL, NULL, &timeout);
                if (ret < 1) {
                        if (ret == 0) {
                                SIM_LOG_ERROR(
                                        obj, 0,
                                        "Timeout when waiting for virtiofs-daemon to start");
                        } else {
                                SIM_LOG_ERROR(
                                        obj, 0,
                                        "Error when waiting for virtiofs-daemon to start. Error: %s",
                                        strerror(errno));
                        }
                        close(efd);
                        return -1;
                }
                close(efd);
                return connect_to_daemon(obj, socket_path);
        }
}

static ssize_t
writeall(int fd, const void *buf, size_t len)
{
        size_t count = 0;

        while (count < len) {
                int i = write(fd, (char *)buf + count, len - count);
                if (i < 1)
                        return i;
                count += i;
        }
        return count;
}

static ssize_t
readall(int fd, void *buf, size_t len)
{
        size_t count = 0;

        while (count < len) {
                int i = read(fd,  (char *)buf + count, len - count);
                if (!i)
                        break;
                if (i < 0)
                        return i;
                count += i;
        }
        return count;
}

static buffer_t
handle(conf_object_t *obj, bytes_t req)
{
        fuse_handler_device_t *fuse = (fuse_handler_device_t *)obj;
        fuse_out_header_t res_header;
        buffer_t res = { 0 };

        if (req.data == NULL) {
                SIM_LOG_ERROR(obj, 0, "NULL buffer passed to fuse handler");
                return res;
        }

        if (!fuse->connection_established) {
                SIM_LOG_ERROR(
                        obj, 0,
                        "Received fuse request will not be processed since no connection has been established to the fuse daemon");
                return res;
        }

        ssize_t ret = writeall(fuse->sfd, req.data, req.len);
        if (ret == -1) {
                SIM_LOG_ERROR(
                        obj, 0,
                        "Could not write to the daemon's unix domain socket");
                unset_connection(fuse);
                return res;
        }

        if (((fuse_in_header_t *)req.data)->opcode == FUSE_FORGET_OPCODE) {
                // No reply
                return res;
        }

        ret = readall(fuse->sfd, &res_header, sizeof(res_header));
        if (ret == -1) {
                SIM_LOG_ERROR(
                        obj, 0,
                        "Could not read fuse header from the fuse daemon's unix domain socket");
                unset_connection(fuse);
                return res;
        }
        if ((res_header.len > MAX_FUSE_PAYLOAD_LEN)
            || (res_header.len < sizeof(res_header))) {
                SIM_LOG_ERROR(
                        obj, 0,
                        "Header len reported by FUSE daemon is not supported");
                unset_connection(fuse);
                return res;
        }

        uint8_t *res_data = MM_MALLOC(res_header.len, uint8_t);
        if (res_data == NULL) {
                SIM_LOG_ERROR(
                        obj, 0,
                        "Could not allocate response buffer for FUSE payload");
                return res;
        }
        ret = readall(fuse->sfd, &res_data[sizeof(res_header)],
                      res_header.len - sizeof(res_header));
        if (ret == -1) {
                SIM_LOG_ERROR(
                        obj, 0,
                        "Could not read fuse payload from the fuse daemon's unix domain socket");
                MM_FREE(res_data);
                unset_connection(fuse);
                return res;
        }
        memcpy(res_data, &res_header, sizeof(res_header));

        res.data = res_data;
        res.len = res_header.len;
        return res;
}

static set_error_t
set_share_attribute(conf_object_t *obj, attr_value_t *val)
{
        fuse_handler_device_t *fuse = (fuse_handler_device_t *)obj;

        if (fuse->connection_established) {
                SIM_attribute_error(
                        "The shared directory cannot be changed once the FUSE daemon has started");
                return Sim_Set_Not_Writable;
        }

        struct stat s;
        if (stat(SIM_attr_string(*val), &s) != 0) {
                SIM_c_attribute_error(
                        "Could not open the specified share attribute: %s",
                        SIM_attr_string(*val));
                return Sim_Set_Illegal_Value;
        }

        if (fuse->share != NULL) {
                MM_FREE(fuse->share);
        }
        fuse->share = MM_STRDUP(SIM_attr_string(*val));

        int ret = -1;
        if (S_ISSOCK(s.st_mode)) {
                ret = connect_to_daemon(obj, fuse->share);
        } else if (S_ISDIR(s.st_mode)) {
                ret = initiate_daemon_connection(obj);
        } else {
                SIM_c_attribute_error(
                        "share must be set to either a directory or a unix domain socket file: %s",
                        SIM_attr_string(*val));
        }

        if (ret != 0) {
                MM_FREE(fuse->share);
                fuse->share = NULL;
                return Sim_Set_Not_Writable;
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_share_attribute(conf_object_t *obj)
{
        fuse_handler_device_t *fuse = (fuse_handler_device_t *)obj;
        return SIM_make_attr_string(fuse->share);
}

static set_error_t
set_daemon_log_file_attribute(conf_object_t *obj, attr_value_t *val)
{
        fuse_handler_device_t *fuse = (fuse_handler_device_t *)obj;

        if (fuse->daemon_pid != -1) {
                SIM_attribute_error(
                        "The daemon log file can not be changed once the FUSE daemon has started");
                return Sim_Set_Not_Writable;
        }
        if (fuse->daemon_log_file != NULL) {
                MM_FREE(fuse->daemon_log_file);
        }
        fuse->daemon_log_file = MM_STRDUP(SIM_attr_string(*val));
        return Sim_Set_Ok;
}

static attr_value_t
get_daemon_log_file_attribute(conf_object_t *obj)
{
        fuse_handler_device_t *fuse = (fuse_handler_device_t *)obj;
        return SIM_make_attr_string(fuse->daemon_log_file);
}

static set_error_t
set_always_cache_attribute(conf_object_t *obj, attr_value_t *val)
{
        fuse_handler_device_t *fuse = (fuse_handler_device_t *)obj;

        if (fuse->connection_established) {
                SIM_attribute_error(
                        "The cache setting can not be changed once the FUSE daemon has started");
                return Sim_Set_Not_Writable;
        }
        fuse->always_cache = SIM_attr_boolean(*val);
        if (fuse->always_cache) {
                SIM_LOG_INFO(
                        2, obj, 0,
                        "Full caching has been enabled. No modifications should be made to the shared directory from the host until the simics process has been terminated");
        }
        return Sim_Set_Ok;
}

static attr_value_t
get_always_cache_attribute(conf_object_t *obj)
{
        fuse_handler_device_t *fuse = (fuse_handler_device_t *)obj;
        return SIM_make_attr_boolean(fuse->always_cache);
}

static attr_value_t
get_connection_established_attribute(conf_object_t *obj)
{
        fuse_handler_device_t *fuse = (fuse_handler_device_t *)obj;
        return SIM_make_attr_boolean(fuse->connection_established);
}

static attr_value_t
get_daemon_pid_attribute(conf_object_t *obj)
{
        fuse_handler_device_t *fuse = (fuse_handler_device_t *)obj;
        return SIM_make_attr_int64(fuse->daemon_pid);
}

void
init_local()
{
        const class_info_t funcs = {
                .alloc = alloc_object,
                .dealloc = dealloc_object,
                .deinit = deinit,
                .short_desc = "FUSE handle device",
                .description =
                        "A device that expects FUSE requests and will reply with FUSE"
                        " responses."
        };
        static const virtiofs_fuse_interface_t virtiofs_fuse_iface = {
                .handle_request = handle,
        };
        conf_class_t *class = SIM_create_class("virtiofs_fuse", &funcs);
        SIM_register_interface(class, VIRTIOFS_FUSE_INTERFACE,
                               &virtiofs_fuse_iface);

        SIM_register_attribute(
                class, "daemon_log_file", get_daemon_log_file_attribute,
                set_daemon_log_file_attribute, Sim_Attr_Pseudo, "s|n",
                "Enable logs for the FUSE daemon and specify the output file for the logs");

        SIM_register_attribute(
                class, "always_cache", get_always_cache_attribute,
                set_always_cache_attribute,
                Sim_Attr_Internal | Sim_Attr_Optional, "b",
                "Enable full caching for FUSE, which increases the performance of "
                "the virtioFS mount point on the guest. NOTE! Only set to true if no "
                "modifications will be done in the shared directory from the host "
                "until the simics process has been terminated. Doing so might result "
                "in data loss. Disabled by default");

        SIM_register_attribute(
                class, "share", get_share_attribute, set_share_attribute,
                Sim_Attr_Required, "s|n",
                "Directory on the host to share with the simulated target or unix domain socket file created by virtiofs daemon");

        SIM_register_attribute(
                class, "connection_established",
                get_connection_established_attribute, NULL,
                Sim_Attr_Pseudo | Sim_Attr_Read_Only, "b",
                "True if connection has been established to FUSE daemon");

        SIM_register_attribute(
                class, "daemon_pid", get_daemon_pid_attribute, NULL,
                Sim_Attr_Pseudo | Sim_Attr_Read_Only, "i",
                "True if connection has been established to FUSE daemon");
}
