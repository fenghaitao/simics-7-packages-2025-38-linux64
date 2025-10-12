/*
  © 2024 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <cassert>
#include <cstdint>
#include <cstring>
#include <pthread.h>

#include <simics/base/log.h>
#include <simics/base/memory.h>
#include <simics/base/transaction.h>
#include <simics/base/types.h>
#include <simics/cc-api.h>

#include <simics/c++/model-iface/external-connection.h>

#include "pcie-shim.h"
#include "ExternalPcieFormat.h"

class ExternalTargetIface
    : public simics::Connect<simics::iface::ExternalConnectionCtlInterface> {
  public:
    explicit ExternalTargetIface(const simics::ConfObjectRef &obj)
        : simics::Connect<simics::iface::ExternalConnectionCtlInterface>(obj)
        {}
};

template <typename T, size_t RING_BUFFER_SIZE> class RingBuffer {
  public:
    size_t free_slots() {
        return RING_BUFFER_SIZE - this->current_size;
    }
    size_t filled_slots() {
        return this->current_size;
    }
    void pop(T *data, size_t size) {
        return this->read(data, size, false);
    }
    void peek(T *data, size_t size) {
        return this->read(data, size, true);
    }
    void push(const T *data, size_t size) {
        if ((size + this->current_size) > RING_BUFFER_SIZE)
            ASSERT(false);

        size_t write_pos = (this->read_pos + this->current_size) % RING_BUFFER_SIZE;
        size_t s1 = size > (RING_BUFFER_SIZE - write_pos) ? (RING_BUFFER_SIZE - write_pos) : size;
        size_t s2 = size - s1;
        std::copy(data, &data[s1], &this->ring_buffer[write_pos]);
        if (s2 > 0)
            std::copy(&data[s1], &data[s1 + s2], &this->ring_buffer[0]);

        this->current_size += size;
    }
  private:
    std::array<T, RING_BUFFER_SIZE> ring_buffer;
    size_t read_pos = 0;
    size_t current_size = 0;

    void read(T *data, size_t size, bool peek) {
        if ((size > this->current_size) || (size == 0))
            ASSERT(false);
        size_t s1 = size > (RING_BUFFER_SIZE - read_pos) ? (RING_BUFFER_SIZE - read_pos) : size;
        size_t s2 = size - s1;
        std::copy(&this->ring_buffer[this->read_pos], &this->ring_buffer[this->read_pos + s1], data);
        if (s2 > 0)
            std::copy(&this->ring_buffer[0], &this->ring_buffer[s2], &data[s1]);
        if (!peek) {
            this->read_pos = (this->read_pos + size) % RING_BUFFER_SIZE;
            this->current_size -= size;
        }   
    }
};

class PcieExternalConnection : public ShimPcie,
                               public simics::iface::ExternalConnectionEventsInterface {
  public:
    explicit PcieExternalConnection(simics::ConfObjectRef obj) : ShimPcie(obj) {}

    static void init_class(simics::ConfClass *cls) {
        /*
        * External connection to another system. All PCIe transactions
        * that are destined to the external target go through this interface and
        * all transactions originating from the external target that shall go upstream
        * to a Simics Root Port or further upstream first enter this interface and 
        * are then converted to Simics PCIe transactions.
        * The connection to the external target can be a named-pipe, TCP, or Unix socket.
        */
        cls->add(simics::Attribute("external_target", "o|n",
                                        "External Target to send request and responses to",
                                        ATTR_CLS_VAR(PcieExternalConnection, external_target)));
        cls->add(simics::Attribute("connection_alive", "b", "Connection with external process is alive",
                                    ATTR_GETTER(PcieExternalConnection, connection_alive), nullptr,
                                    Sim_Attr_Pseudo));
        cls->add(simics::iface::ExternalConnectionEventsInterface::Info());
        REGISTER_AFTER_CALL(&PcieExternalConnection::handle_on_input);
        ShimPcie::init_class(cls);
    }
    uint64 con_id = 0;
    ExternalTargetIface external_target {this->obj()};
    bool connection_alive() { return this->con_id > 0; }
  private:
    void
    forward_message(write_completion_t completion,
                    uint64_t addr,
                    pcie_message_type_t mtype,
                    pcie_msg_route_t route,
                    uint16_t bdf,
                    std::vector<uint8_t> &payload) override;

    void
    forward_mem_read(read_completion_t completion, uint64_t addr,
                     size_t size) override;

    void
    forward_mem_write(write_completion_t completion,
                      uint64_t addr, std::vector<uint8_t> &buf) override;

    void
    forward_cfg_write(write_completion_t completion,
                      bool type0, uint16_t bdf, uint16_t ofs,
                      std::vector<uint8_t> &buf) override;

    void
    forward_cfg_read(read_completion_t completion,
                     bool type0, uint16_t bdf, uint16_t ofs,
                     size_t size) override;

    void
    forward_io_write(write_completion_t completion,
                     uint64_t addr, std::vector<uint8_t> &buf) override;

    void
    forward_io_read(read_completion_t completion,
                    uint64_t addr, size_t size) override;

    void hot_reset() override;

    void
    read_input(void *buf, size_t size);
    void
    write_async(bytes_t bytes);
    bool
    is_read_tag(uint64 tag);
    bool
    is_write_tag(uint64 tag);
    bool
    is_message_tag(uint64 tag);
    bool
    is_valid_tag(uint64 tag);
    void
    handle_response(struct external_packet &packet);
    void
    handle_request(struct external_packet &packet);
    void
    handle_mem_request(struct external_packet &packet,
                       struct external_request &request);
    void
    handle_mem_read_request(struct external_packet &packet,
                            struct external_request &request,
                            struct pcie_tlp_mem_header &mem);
    void
    handle_mem_write_request(struct external_packet &packet,
                             struct external_request &request,
                             struct pcie_tlp_mem_header &mem);
    void
    send_mem_read_response(uint64_t tag, std::vector<uint8_t> &buf);
    void
    send_write_response(uint64_t tag);
    void
    send_failure_response(uint64_t tag);

    bool
    validate_paket(struct external_packet &packet);
    void
    wait_for_response(uint64_t tag);

    void handle_on_input();
    /* External connection event interface */
    void on_accept(conf_object_t *server, uint64 id) override;
    void on_input(lang_void *cookie) override;
    void can_write(lang_void *cookie) override;

    uint64 tag = 0;
    std::map<uint64_t, read_completion_t> outstanding_reads;
    std::map<uint64_t, write_completion_t> outstanding_writes;
    std::map<uint64_t, write_completion_t> outstanding_messages;

    bool packet_ready(bool lock_held);
    pthread_mutex_t read_mutex = PTHREAD_MUTEX_INITIALIZER;
    pthread_cond_t read_ready_cond = PTHREAD_COND_INITIALIZER;
    bool wait_for_read = false;
    bool signal_fired = false;

    /* Ring buffer */
    static const size_t RING_BUFFER_SIZE = 0x100000;
    RingBuffer<uint8_t, RING_BUFFER_SIZE> ring_buffer;
};

void
PcieExternalConnection::forward_message(write_completion_t completion,
                                        uint64_t addr,
                                        pcie_message_type_t mtype,
                                        pcie_msg_route_t route,
                                        uint16_t bdf,
                                        std::vector<uint8_t> &payload) {
    size_t size = 0;
    size += sizeof(struct external_packet);
    size += sizeof(struct external_request);
    size += sizeof(struct pcie_tlp_msg_header);
    size += payload.size();

    std::vector<uint8_t> packet_buf(size);
    size_t ofs = 0;

    struct external_packet packet;
    packet.type = EXTERNAL_TYPE_REQUEST;
    packet.tag = ++this->tag;
    packet.packet_len = packet_buf.size();
    memcpy(&packet_buf[ofs], &packet, sizeof(packet));
    ofs += sizeof(packet);

    struct external_request request;
    request.pcie_hdr.type = PCIE_TLP_TYPE_MSG;
    request.pcie_hdr.addr = addr;
    memcpy(&packet_buf[ofs], &request, sizeof(request));
    ofs += sizeof(request);

    struct pcie_tlp_msg_header msg;
    msg.destination_id = bdf;
    msg.msg_type = mtype;
    msg.route = route;
    msg.payload_len = payload.size();
    memcpy(&packet_buf[ofs], &msg, sizeof(msg));
    ofs += sizeof(msg);

    memcpy(&packet_buf[ofs], payload.data(), payload.size());

    SIM_LOG_INFO(3, obj(), 0,
        "Forward message %s %s",
        ShimPcie::msg_type_str(mtype),
        ShimPcie::msg_route_str(route));

    bytes_t bytes = {packet_buf.data(), packet_buf.size()};
    this->outstanding_messages[this->tag] = std::move(completion);
    try {
        this->write_async(bytes);
        this->wait_for_response(packet.tag);
    } catch (const std::runtime_error& e) {
        SIM_LOG_INFO(1, obj(), 0, "%s", e.what());
        SIM_LOG_ERROR(obj(), 0, "Error sending to external connection %s\n", e.what());
        this->outstanding_messages.erase(this->tag);
        this->outstanding_messages[this->tag](Sim_PE_IO_Error);
    }
}

void
PcieExternalConnection::forward_mem_read(read_completion_t completion, uint64_t addr,
                                         size_t read_size) {
    size_t size = 0;
    size += sizeof(struct external_packet);
    size += sizeof(struct external_request);
    size += sizeof(struct pcie_tlp_mem_header);

    std::vector<uint8_t> packet_buf(size);
    size_t ofs = 0;

    struct external_packet packet;
    packet.type = EXTERNAL_TYPE_REQUEST;
    packet.tag = ++this->tag;
    packet.packet_len = packet_buf.size();
    memcpy(&packet_buf[ofs], &packet, sizeof(packet));
    ofs += sizeof(packet);

    struct external_request request;
    request.pcie_hdr.type = PCIE_TLP_TYPE_MEM;
    request.pcie_hdr.addr = addr;
    memcpy(&packet_buf[ofs], &request, sizeof(request));
    ofs += sizeof(request);

    struct pcie_tlp_mem_header mem;
    mem.rnw = true;
    mem.len = read_size;
    memcpy(&packet_buf[ofs], &mem, sizeof(mem));
    ofs += sizeof(mem);

    bytes_t bytes = {packet_buf.data(), packet_buf.size()};

    SIM_LOG_INFO(4, obj(), 0,
        "Forward MEM read @ 0x%zx-0x%zx",
        static_cast<size_t>(addr),
        static_cast<size_t>(addr + read_size - 1));

    this->outstanding_reads[this->tag] = std::move(completion);
    try {
        this->write_async(bytes);
        this->wait_for_response(packet.tag);
    } catch (const std::runtime_error& e) {
        SIM_LOG_INFO(1, obj(), 0, "%s", e.what());
        SIM_LOG_ERROR(obj(), 0, "Error sending to external connection %s\n", e.what());
        SIM_LOG_ERROR(obj(), 0, "Error communicating over external connection %s\n", e.what());
        this->outstanding_reads.erase(this->tag);
        std::vector<uint8_t> buf(0);
        this->outstanding_reads[this->tag](Sim_PE_IO_Error, buf);
    }
}

void
PcieExternalConnection::forward_mem_write(write_completion_t completion, uint64_t addr,
                                          std::vector<uint8_t> &buf) {
    size_t size = 0;
    size += sizeof(struct external_packet);
    size += sizeof(struct external_request);
    size += sizeof(struct pcie_tlp_mem_header);
    size += buf.size();

    std::vector<uint8_t> packet_buf(size);
    size_t ofs = 0;

    struct external_packet packet;
    packet.type = EXTERNAL_TYPE_REQUEST;
    packet.tag = ++this->tag;
    packet.packet_len = packet_buf.size();
    memcpy(&packet_buf[ofs], &packet, sizeof(packet));
    ofs += sizeof(packet);

    struct external_request request;
    request.pcie_hdr.type = PCIE_TLP_TYPE_MEM;
    request.pcie_hdr.addr = addr;
    memcpy(&packet_buf[ofs], &request, sizeof(request));
    ofs += sizeof(request);

    struct pcie_tlp_mem_header mem;
    mem.rnw = false;
    mem.len = buf.size();
    memcpy(&packet_buf[ofs], &mem, sizeof(mem));
    ofs += sizeof(mem);

    memcpy(&packet_buf[ofs], buf.data(), buf.size());

    SIM_LOG_INFO(4, obj(), 0,
        "Forward MEM write @ 0x%zx-0x%zx",
        static_cast<size_t>(addr),
        static_cast<size_t>(addr + buf.size() - 1));

    bytes_t bytes = {packet_buf.data(), packet_buf.size()};
    this->outstanding_writes[this->tag] = std::move(completion);
    try {
        this->write_async(bytes);
        this->wait_for_response(packet.tag);
    } catch (const std::runtime_error& e) {
        SIM_LOG_INFO(1, obj(), 0, "%s", e.what());
        SIM_LOG_ERROR(obj(), 0, "Error sending to external connection %s\n", e.what());
        SIM_LOG_ERROR(obj(), 0, "Error communicating over external connection %s\n", e.what());
        this->outstanding_writes.erase(this->tag);
        this->outstanding_writes[this->tag](Sim_PE_IO_Error);
    }
}

void
PcieExternalConnection::forward_cfg_write(write_completion_t completion,
                                          bool type0, uint16_t bdf, uint16_t write_ofs,
                                          std::vector<uint8_t> &buf) {
    size_t size = 0;
    size += sizeof(struct external_packet);
    size += sizeof(struct external_request);
    size += sizeof(struct pcie_tlp_cfg_header);
    size += buf.size();

    std::vector<uint8_t> packet_buf(size);
    size_t ofs = 0;

    struct external_packet packet;
    packet.type = EXTERNAL_TYPE_REQUEST;
    packet.tag = ++this->tag;
    packet.packet_len = packet_buf.size();
    memcpy(&packet_buf[ofs], &packet, sizeof(packet));
    ofs += sizeof(packet);

    struct external_request request;
    request.pcie_hdr.type = PCIE_TLP_TYPE_CFG;
    request.pcie_hdr.addr = 0;  // Unused
    memcpy(&packet_buf[ofs], &request, sizeof(request));
    ofs += sizeof(request);

    struct pcie_tlp_cfg_header cfg;
    cfg.rnw = false;
    cfg.type0 = type0;
    cfg.bdf = bdf;
    cfg.ofs = write_ofs;
    cfg.payload_len = buf.size();
    memcpy(&packet_buf[ofs], &cfg, sizeof(cfg));
    ofs += sizeof(cfg);

    memcpy(&packet_buf[ofs], buf.data(), buf.size());

    uint64_t addr = write_ofs;
    if (!type0)
        addr += (static_cast<uint64_t>(bdf)) << 16;
    SIM_LOG_INFO(4, obj(), 0,
        "Forward CFG Type%d write @ 0x%zx-0x%zx",
        type0 ? 0 : 1,
        static_cast<size_t>(addr),
        static_cast<size_t>(addr + buf.size() - 1));

    bytes_t bytes = {packet_buf.data(), packet_buf.size()};
    this->outstanding_writes[this->tag] = std::move(completion);
    try {
        this->write_async(bytes);
        this->wait_for_response(packet.tag);
    } catch (const std::runtime_error& e) {
        SIM_LOG_INFO(1, obj(), 0, "%s", e.what());
        SIM_LOG_ERROR(obj(), 0, "Error communicating over external connection %s\n", e.what());
        this->outstanding_writes.erase(this->tag);
        this->outstanding_writes[this->tag](Sim_PE_IO_Error);
    }
}

void
PcieExternalConnection::forward_cfg_read(read_completion_t completion,
                                         bool type0, uint16_t bdf,
                                         uint16_t read_ofs, size_t read_size) {
    size_t size = 0;
    size += sizeof(struct external_packet);
    size += sizeof(struct external_request);
    size += sizeof(struct pcie_tlp_cfg_header);

    std::vector<uint8_t> packet_buf(size);
    size_t ofs = 0;

    struct external_packet packet;

    packet.type = EXTERNAL_TYPE_REQUEST;
    packet.tag = ++this->tag;
    packet.packet_len = packet_buf.size();
    memcpy(&packet_buf[ofs], &packet, sizeof(packet));
    ofs += sizeof(packet);

    struct external_request request;
    request.pcie_hdr.type = PCIE_TLP_TYPE_CFG;
    request.pcie_hdr.addr = 0;  // Unused
    memcpy(&packet_buf[ofs], &request, sizeof(request));
    ofs += sizeof(request);

    struct pcie_tlp_cfg_header cfg;
    cfg.rnw = true;
    cfg.type0 = type0;
    cfg.bdf = bdf;
    cfg.ofs = read_ofs;
    cfg.payload_len = read_size;
    memcpy(&packet_buf[ofs], &cfg, sizeof(cfg));
    ofs += sizeof(cfg);

    uint64_t addr = read_ofs;
    if (!type0)
        addr += (static_cast<uint64_t>(bdf)) << 16;

    SIM_LOG_INFO(4, obj(), 0,
        "Forwards CFG Type%d read @ 0x%zx-0x%zx",
        type0 ? 0 : 1,
        static_cast<size_t>(addr),
        static_cast<size_t>(addr + read_size - 1));

    bytes_t bytes = {packet_buf.data(), packet_buf.size()};
    this->outstanding_reads[this->tag] = std::move(completion);
    try {
        this->write_async(bytes);
        this->wait_for_response(packet.tag);
    } catch (const std::runtime_error& e) {
        SIM_LOG_INFO(1, obj(), 0, "%s", e.what());
        SIM_LOG_ERROR(obj(), 0, "Error communicating over external connection %s\n", e.what());
        this->outstanding_reads.erase(this->tag);
        std::vector<uint8_t> buf(0);
        this->outstanding_reads[this->tag](Sim_PE_IO_Error, buf);
    }
}

void
PcieExternalConnection::forward_io_write(write_completion_t completion,
                                         uint64_t addr, std::vector<uint8_t> &buf) {
    size_t size = 0;
    size += sizeof(struct external_packet);
    size += sizeof(struct external_request);
    size += sizeof(struct pcie_tlp_io_header);
    size += buf.size();

    std::vector<uint8_t> packet_buf(size);
    size_t ofs = 0;
    struct external_packet packet;

    packet.type = EXTERNAL_TYPE_REQUEST;
    packet.tag = ++this->tag;
    packet.packet_len = packet_buf.size();
    memcpy(&packet_buf[ofs], &packet, sizeof(packet));
    ofs = sizeof(packet);

    struct external_request request;
    request.pcie_hdr.type = PCIE_TLP_TYPE_IO;
    request.pcie_hdr.addr = addr;
    memcpy(&packet_buf[ofs], &request, sizeof(request));
    ofs += sizeof(request);

    struct pcie_tlp_io_header io;
    io.rnw = false;
    io.len = buf.size();
    memcpy(&packet_buf[ofs], &io, sizeof(io));
    ofs += sizeof(io);

    memcpy(&packet_buf[ofs], buf.data(), buf.size());

    SIM_LOG_INFO(4, obj(), 0,
        "Forward IO write @ 0x%zx-0x%zx",
        static_cast<size_t>(addr),
        static_cast<size_t>(addr + buf.size() - 1));

    bytes_t bytes = {packet_buf.data(), packet_buf.size()};
    this->outstanding_writes[this->tag] = std::move(completion);
    try {
        this->write_async(bytes);
        this->wait_for_response(packet.tag);
    } catch (const std::runtime_error& e) {
        SIM_LOG_INFO(1, obj(), 0, "%s", e.what());
        SIM_LOG_ERROR(obj(), 0, "Error sending to external connection %s\n", e.what());
        this->outstanding_writes.erase(this->tag);
        this->outstanding_writes[this->tag](Sim_PE_IO_Error);
    }
}

void
PcieExternalConnection::forward_io_read(read_completion_t completion,
                                        uint64_t addr, size_t read_size) {
    size_t size = 0;
    size += sizeof(struct external_packet);
    size += sizeof(struct external_request);
    size += sizeof(struct pcie_tlp_io_header);

    std::vector<uint8_t> packet_buf(size);
    size_t ofs = 0;

    struct external_packet packet;
    packet.type = EXTERNAL_TYPE_REQUEST;
    packet.tag = ++this->tag;
    packet.packet_len = packet_buf.size();
    memcpy(&packet_buf[ofs], &packet, sizeof(packet));
    ofs += sizeof(packet);

    struct external_request request;
    request.pcie_hdr.type = PCIE_TLP_TYPE_IO;
    request.pcie_hdr.addr = addr;
    memcpy(&packet_buf[ofs], &request, sizeof(request));
    ofs += sizeof(request);

    struct pcie_tlp_io_header io;
    io.rnw = true;
    io.len = read_size;
    memcpy(&packet_buf[ofs], &io, sizeof(io));
    ofs += sizeof(io);

    bytes_t bytes = {packet_buf.data(), packet_buf.size()};

    SIM_LOG_INFO(4, obj(), 0,
        "Forward IO read @ 0x%zx-0x%zx",
        static_cast<size_t>(addr),
        static_cast<size_t>(addr + read_size - 1));

    this->outstanding_reads[this->tag] = std::move(completion);

    try {
        this->write_async(bytes);
        this->wait_for_response(packet.tag);
    } catch (const std::runtime_error& e) {
        SIM_LOG_INFO(1, obj(), 0, "%s", e.what());
        SIM_LOG_ERROR(obj(), 0, "Error communicating over external connection %s\n", e.what());
        this->outstanding_reads.erase(this->tag);
        std::vector<uint8_t> buf(0);
        this->outstanding_reads[this->tag](Sim_PE_IO_Error, buf);
    }
}

void
PcieExternalConnection::hot_reset() {
    SIM_LOG_UNIMPLEMENTED(1, obj(), 0, "Hot-reset unimplemented");
}

void
PcieExternalConnection::on_accept(conf_object_t *server, uint64 id) {
    if (this->con_id > 0) {
        SIM_LOG_ERROR(obj(), 0, "Connection already established\n");
        return;
    }

    SIM_LOG_INFO(1, obj(), 0,
        "Connection accept call from server %s id=%zu",
        SIM_object_name(server), static_cast<size_t>(id));

    this->external_target.set(server);

    this->con_id = id;
    this->external_target.iface().accept(id, this, false /* Nonblocking read*/);
    this->external_target.iface().notify(this, Sim_NM_Read, Sim_EM_Thread, true);
}

void
PcieExternalConnection::read_input(void *buf, size_t size) {
    pthread_mutex_lock(&this->read_mutex);
    if (this->ring_buffer.filled_slots() < size) {
        SIM_LOG_ERROR(obj(), 0, "read_input filled slots %zu < %zu",
            this->ring_buffer.filled_slots(), size);
        ASSERT(false);
    }
    this->ring_buffer.pop(static_cast<uint8_t*>(buf), size);
    pthread_mutex_unlock(&this->read_mutex);
}

void
PcieExternalConnection::write_async(bytes_t bytes) {
    if (this->connection_alive()) {
        SIM_LOG_INFO(4, obj(), 0, "Writing 0x%zx bytes to external connection", bytes.len);
        this->external_target.iface().write_async(this, bytes);
    } else {
        SIM_LOG_ERROR(obj(), 0, "Connection is not alive, cannot write\n");
        throw std::runtime_error("Connection is not alive, cannot write");
    }
}

bool
PcieExternalConnection::is_read_tag(uint64 tag) {
    return (this->outstanding_reads.find(tag) != this->outstanding_reads.end());
}

bool
PcieExternalConnection::is_write_tag(uint64 tag) {
    return (this->outstanding_writes.find(tag) != this->outstanding_writes.end());
}
bool
PcieExternalConnection::is_message_tag(uint64 tag) {
    return (this->outstanding_messages.find(tag) != this->outstanding_messages.end());
}

bool
PcieExternalConnection::is_valid_tag(uint64 tag) {
    return (this->is_read_tag(tag) ||
            this->is_write_tag(tag) ||
            this->is_message_tag(tag));
}

void
PcieExternalConnection::handle_response(struct external_packet &packet)
{
    struct external_response response;

    this->read_input(&response, sizeof(response));
    
    if (this->is_read_tag(packet.tag)) {
        auto node = this->outstanding_reads.extract(packet.tag);
        const auto &completion = node.mapped();

        if (response.ret == EXTERNAL_RESPONSE_TYPE_SUCCESS) {
            std::vector<uint8_t> buf(response.payload_len);

            this->read_input(buf.data(), buf.size());
            completion(Sim_PE_No_Exception, buf);
        } else {
            std::vector<uint8_t> buf(0);
            completion(Sim_PE_IO_Error, buf);
        }
    } else if (this->is_write_tag(packet.tag)) {
        auto node = this->outstanding_writes.extract(packet.tag);
        const auto &completion = node.mapped();

        response.ret == EXTERNAL_RESPONSE_TYPE_SUCCESS ? completion(Sim_PE_No_Exception)
                                                       : completion(Sim_PE_IO_Error);
    } else if (this->is_message_tag(packet.tag)) {
        auto node = this->outstanding_messages.extract(packet.tag);
        const auto &completion = node.mapped();

        response.ret == EXTERNAL_RESPONSE_TYPE_SUCCESS ? completion(Sim_PE_No_Exception)
                                                       : completion(Sim_PE_IO_Error);
    } else {
        SIM_LOG_ERROR(obj(), 0, "Unknown tag 0x%zx\n", static_cast<size_t>(packet.tag));
        this->external_target.iface().close(this);
    }
}

void
PcieExternalConnection::send_mem_read_response(uint64_t tag, std::vector<uint8_t> &buf) {
    size_t size = 0;
    size += sizeof(struct external_packet);
    size += sizeof(struct external_response);
    size += buf.size();

    std::vector<uint8_t> packet_buf(size);
    size_t ofs = 0;

    struct external_packet packet;

    packet.type = EXTERNAL_TYPE_RESPONSE;
    packet.packet_len = packet_buf.size();
    packet.tag = tag;
    memcpy(packet_buf.data() + ofs, &packet, sizeof(packet));
    ofs += sizeof(packet);

    struct external_response response;
    response.ret = EXTERNAL_RESPONSE_TYPE_SUCCESS;
    response.payload_len = buf.size();
    memcpy(packet_buf.data() + ofs, &response, sizeof(response));
    ofs += sizeof(response);

    memcpy(packet_buf.data() + ofs, buf.data(), buf.size());

    bytes_t bytes = {packet_buf.data(), packet_buf.size()};
    try {
        this->write_async(bytes);
    } catch (const std::runtime_error& e) {
        SIM_LOG_INFO(1, obj(), 0, "send_write_response %s", e.what());
        SIM_LOG_ERROR(obj(), 0, "Error sending to external connection %s\n", e.what());
    }
}

void
PcieExternalConnection::send_write_response(uint64_t tag) {
    size_t size = 0;
    size += sizeof(struct external_packet);
    size += sizeof(struct external_response);

    std::vector<uint8_t> packet_buf(size);
    size_t ofs = 0;

    struct external_packet packet;

    packet.type = EXTERNAL_TYPE_RESPONSE;
    packet.packet_len = packet_buf.size();
    packet.tag = tag;
    memcpy(packet_buf.data() + ofs, &packet, sizeof(packet));
    ofs += sizeof(packet);

    struct external_response response;
    response.ret = EXTERNAL_RESPONSE_TYPE_SUCCESS;
    response.payload_len = 0;
    memcpy(packet_buf.data() + ofs, &response, sizeof(response));
    ofs += sizeof(response);

    bytes_t bytes = {packet_buf.data(), packet_buf.size()};
    try {
        this->write_async(bytes);
    } catch (const std::runtime_error& e) {
        SIM_LOG_INFO(1, obj(), 0, "send_write_response %s", e.what());
        SIM_LOG_ERROR(obj(), 0, "Error sending to external connection %s\n", e.what());
    }
}

void
PcieExternalConnection::send_failure_response(uint64_t tag) {
    size_t size = sizeof(struct external_packet) + sizeof(struct external_response);

    std::vector<uint8_t> packet_buf(size);
    size_t ofs = 0;

    struct external_packet packet;

    packet.type = EXTERNAL_TYPE_RESPONSE;
    packet.packet_len = packet_buf.size();
    packet.tag = tag;
    memcpy(packet_buf.data() + ofs, &packet, sizeof(packet));
    ofs += sizeof(packet);

    struct external_response response;
    response.ret = EXTERNAL_RESPONSE_TYPE_ERROR;
    response.payload_len = 0;
    memcpy(packet_buf.data() + ofs, &response, sizeof(response));

    bytes_t bytes = {packet_buf.data(), packet_buf.size()};
    try {
        this->write_async(bytes);
    } catch (const std::runtime_error& e) {
        SIM_LOG_INFO(1, obj(), 0, "send_failure_response %s", e.what());
        SIM_LOG_ERROR(obj(), 0, "Error sending to external connection %s\n", e.what());
    }
}

void
PcieExternalConnection::handle_mem_read_request(struct external_packet &packet,
                                                struct external_request &request,
                                                struct pcie_tlp_mem_header &mem) {
    uint64 addr = request.pcie_hdr.addr;
    size_t size = mem.len;

    SIM_LOG_INFO(4, obj(), 0,
        "Received upstream MEM read @ 0x%zx-0x%zx",
        static_cast<size_t>(addr),
        static_cast<size_t>(addr + size - 1));

    std::vector<uint8_t> buf(size);
    auto ret = this->upstream_mem_read(addr, buf);
    if (ret == Sim_PE_No_Exception) {
        SIM_LOG_INFO(4, obj(), 0,
            "upstream MEM read @ 0x%zx-0x%zx succeeded sending response",
            static_cast<size_t>(addr),
            static_cast<size_t>(addr + size - 1));
        this->send_mem_read_response(packet.tag, buf);
    } else {
        SIM_LOG_INFO(4, obj(), 0,
            "upstream MEM read @ 0x%zx-0x%zx failed sending response",
            static_cast<size_t>(addr),
            static_cast<size_t>(addr + size - 1));
        this->send_failure_response(packet.tag);
    }
}

void
PcieExternalConnection::handle_mem_write_request(struct external_packet &packet,
                                                 struct external_request &request,
                                                 struct pcie_tlp_mem_header &mem) {
    uint64 addr = request.pcie_hdr.addr;
    size_t size = mem.len;
    size_t expected_size = packet.packet_len - sizeof(struct external_packet) -
                          sizeof(struct external_request) - sizeof(struct pcie_tlp_mem_header);
    if (expected_size != size) {
        SIM_LOG_ERROR(obj(), 0,
    "Invalid memory write request, expected size=%zu, size=%zu\n",
        expected_size, size);
        this->external_target.iface().close(this);
        return;
    }

    SIM_LOG_INFO(4, obj(), 0,
        "Received upstream MEM write @ 0x%zx-0x%zx",
        static_cast<size_t>(addr),
        static_cast<size_t>(addr + size - 1));

    std::vector<uint8_t> buf(size);
    this->read_input(buf.data(), buf.size());

    auto ret = this->upstream_mem_write(addr, buf);
    if (ret == Sim_PE_No_Exception) {
        SIM_LOG_INFO(4, obj(), 0,
            "upstream MEM write @ 0x%zx-0x%zx succeeded sending response",
            static_cast<size_t>(addr),
            static_cast<size_t>(addr + size - 1));
        this->send_write_response(packet.tag);
    } else {
        SIM_LOG_INFO(4, obj(), 0,
            "upstream MEM write @ 0x%zx-0x%zx failed sending response %d",
            static_cast<size_t>(addr),
            static_cast<size_t>(addr + size - 1),
            ret);
        this->send_failure_response(packet.tag);
    }
}

void
PcieExternalConnection::handle_mem_request(struct external_packet &packet,
                                           struct external_request &request) {
    struct pcie_tlp_mem_header mem;

    this->read_input(&mem, sizeof(mem));

    if (mem.rnw)
        this->handle_mem_read_request(packet, request, mem);
    else
        this->handle_mem_write_request(packet, request, mem);
}

void
PcieExternalConnection::handle_request(struct external_packet &packet)
{
    struct external_request request;

    this->read_input(&request, sizeof(request));

    if (request.pcie_hdr.type == PCIE_TLP_TYPE_MEM) {
        this->handle_mem_request(packet, request);
    } else if (request.pcie_hdr.type == PCIE_TLP_TYPE_MSG) {
        SIM_LOG_UNIMPLEMENTED(1, obj(), 0, "Upstream Messaging unimplemented");
    } else {
        SIM_LOG_ERROR(obj(),
            0, "Unknown packet type %u\n",
            request.pcie_hdr.type);
        this->external_target.iface().close(this);
    }
}

bool
PcieExternalConnection::validate_paket(struct external_packet &packet) {
    if (packet.type != EXTERNAL_TYPE_RESPONSE && packet.type != EXTERNAL_TYPE_REQUEST) {
        SIM_LOG_ERROR(obj(), 0, "Unknown packet type %d\n", packet.type);
        this->external_target.iface().close(this);
        return false;
    }
    if (packet.packet_len > this->RING_BUFFER_SIZE) {
        SIM_LOG_ERROR(obj(), 0, "Packet too large 0x%zx\n", (size_t)packet.packet_len);
        this->external_target.iface().close(this);
        return false;
    }
    if (packet.type == EXTERNAL_TYPE_RESPONSE) {
        if (this->is_valid_tag(packet.tag)) {
            return true;
        } else {
            SIM_LOG_ERROR(obj(), 0, "Unknown packet type %d\n", packet.type);
            this->external_target.iface().close(this);
            return false;
        }
    } else if (packet.type == EXTERNAL_TYPE_REQUEST) {
        return true;
    } else {
        SIM_LOG_ERROR(obj(), 0, "Unknown packet type %d\n", packet.type);
        this->external_target.iface().close(this);
        return false;
    }
}

bool
PcieExternalConnection::packet_ready(bool lock_held)
{
    struct external_packet packet;

    /* Check if ring_buffer at least contains external_packet header */
    if (!lock_held)
        pthread_mutex_lock(&this->read_mutex);
    /* coverity[missing_lock] */
    if (this->ring_buffer.filled_slots() < sizeof(packet)) {
        if (!lock_held)
            pthread_mutex_unlock(&this->read_mutex);
        return false;
    }

    /* Check if ring_buffer contains a full packet */
    this->ring_buffer.peek(reinterpret_cast<uint8_t *>(&packet),
                    sizeof(packet));
    bool ret = packet.packet_len <= this->ring_buffer.filled_slots();
    if (!lock_held)
        pthread_mutex_unlock(&this->read_mutex);
    return ret;
}

void
PcieExternalConnection::wait_for_response(uint64_t tag) {
    SIM_LOG_INFO(4, obj(), 0,
        "Waiting for response from external connection with tag %zu", tag);

    struct external_packet packet;
    bool found = false;

    do {
        pthread_mutex_lock(&this->read_mutex);
        this->wait_for_read = true;
        while (!this->packet_ready(true)) {
            this->signal_fired = false;
            while (!this->signal_fired)
                pthread_cond_wait(&this->read_ready_cond, &this->read_mutex);
        }
        this->wait_for_read = false;
        pthread_mutex_unlock(&this->read_mutex);

        if (!this->connection_alive()) {
            throw std::runtime_error("Connection is not alive, cannot wait for response");
        }

        this->read_input(&packet, sizeof(packet));

        SIM_LOG_INFO(4, obj(), 0, "Received input from external connection");
        if (!this->validate_paket(packet))
            ASSERT(false);

        if (packet.type == EXTERNAL_TYPE_RESPONSE) {
            SIM_LOG_INFO(4, obj(), 0,
            "Got response from external connection with tag %zu", tag);
            this->handle_response(packet);
            if (packet.tag == tag)
                found = true;
        } else {
            SIM_LOG_INFO(4, obj(), 0,
            "Got request from external connection with tag %zu", tag);
            this->handle_request(packet);
        }
    } while (!found);
}

void
PcieExternalConnection::handle_on_input() {
    struct external_packet packet;
    if (!this->packet_ready(false))
        return;

    this->read_input(&packet, sizeof(packet));
    if (!this->validate_paket(packet))
        return;
    if (packet.type == EXTERNAL_TYPE_RESPONSE)
        this->handle_response(packet);
    else
        this->handle_request(packet);
}

void
PcieExternalConnection::on_input(lang_void *cookie) {
    uint8_t buf[RING_BUFFER_SIZE];

    pthread_mutex_lock(&this->read_mutex);
    buffer_t bytes = {buf, this->ring_buffer.free_slots()};
    pthread_mutex_unlock(&this->read_mutex);

    if (!this->connection_alive())
        return;

    ssize_t len = this->external_target.iface().read(this, bytes);
    if (len == -2)  /* no data, would block */
        return;

    if (len == -1 || len == 0) {  /* -1 = error, 0 = closed by peer */
        this->con_id = 0;
        this->external_target.iface().close(this);

        /* Wake up waiting thread so it can exit */
        pthread_mutex_lock(&this->read_mutex);
        if (this->wait_for_read) {
            this->signal_fired = true;
            pthread_cond_signal(&this->read_ready_cond);
        }
        pthread_mutex_unlock(&this->read_mutex);
        return;
    }

    pthread_mutex_lock(&this->read_mutex);
    this->ring_buffer.push(buf, len);
    if (this->wait_for_read) {
        this->signal_fired = true;
        pthread_cond_signal(&this->read_ready_cond);
        pthread_mutex_unlock(&this->read_mutex);
    } else {
        pthread_mutex_unlock(&this->read_mutex);
        AFTER_CALL(this, static_cast<cycles_t>(0),
        &PcieExternalConnection::handle_on_input, obj());
    }
}

void
PcieExternalConnection::can_write(lang_void *cookie) {
    SIM_LOG_UNIMPLEMENTED(1, obj(), 0, "External-connection can_write() unimplemented");
}

extern "C" void init_external_connection() try {
    simics::make_class<PcieExternalConnection>(
    "sample-pcie-external-connection",
    "a PCIe Shim with an external connection",
    "Shim that forwards Simics PCIe transaction to an external entity");
} catch(const std::exception& e) {
    std::cerr << e.what() << std::endl;
}
