# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from getpass import getuser
import hashlib
import json
import os
import platform
import sys
import time
import urllib.request
from uuid import uuid4

# Environment variables which affect sender. Please check source code
# to figure out what they do:
ENV_SIMICS_TELEMETRY_LOG_FILE = "SIMICS_TELEMETRY_LOG_FILE"
ENV_SIMICS_TELEMETRY_ALWAYS_SEND_DATA = "SIMICS_TELEMETRY_ALWAYS_SEND_DATA"
# NB: ENV_SIMICS_TELEMETRY_DISABLE_SENDING is internal and is to be used
# only by Simics continuous integration system:
ENV_SIMICS_TELEMETRY_DISABLE_SENDING = "SIMICS_TELEMETRY_DISABLE_SENDING"
ENV_SIMICS_TELEMETRY_DUMP_FILE = "SIMICS_TELEMETRY_DUMP_FILE"

if ENV_SIMICS_TELEMETRY_LOG_FILE in os.environ:
    debug = True
    # NB: until the full path is specified, the file with debug log is
    # created in the current directory of the sender process which may
    # differ from Simics project directory (see tracker.py).
    debug_fname = os.environ["SIMICS_TELEMETRY_LOG_FILE"]
else:
    debug = False
    debug_fname = 'telemetry-sender-debug.txt'

if debug:
    sys.stdout = sys.stderr = open(debug_fname, 'w')
    def log(msg):
        if not msg.endswith("\n"):
            msg += "\n"
        sys.stdout.write(msg)
        sys.stdout.flush()
else:
    def log(msg):
        return

def log_stderr(msg):
    if not msg.endswith("\n"):
        msg += "\n"
    sys.stderr.write(msg)

STATS_URL = 'http://simics-statistics.intel.com/api/v0.1/'

if ENV_SIMICS_TELEMETRY_ALWAYS_SEND_DATA in os.environ:
    is_send_data = True
else:
    # ENV_SIMICS_TELEMETRY_DISABLE_SENDING is used by Simics continuous
    # integration to disable sending of telemetry data: telemetry is
    # to analyze users' usage, not our own.
    is_send_data = ENV_SIMICS_TELEMETRY_DISABLE_SENDING not in os.environ

# Function to get/send data. Returns tuple with status code and data
# on success, None if exception was encountered.
def api_post(json_payload, apiTarget):
    try:
        url = STATS_URL + apiTarget
        log(f'Accessing {url}')
        req = urllib.request.Request(
            url,
            data=json.dumps(json_payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'})
        response = urllib.request.urlopen(req, timeout=5)  # nosec
        log(f"Access status: {response.getcode()}")
        return (response.getcode(), response.read())
    except Exception as e:
        log_stderr(f"EXCEPTION: {repr(e)}")

def api_get(apiTarget):
    try:
        req = urllib.request.Request(STATS_URL + apiTarget)
        response = urllib.request.urlopen(req, timeout=5)  # nosec
        return response.read()
    except Exception as e:
        log_stderr(f"EXCEPTION: {repr(e)}")

def amend_data(collected_stats):
    if collected_stats['core.session'].get('stop_time') is None:
        collected_stats['core.session']['stop_time'] = time.time()
    if collected_stats['core.session']['start_time'] is not None:
        startTime = collected_stats['core.session']['start_time']
        finishTime = collected_stats['core.session']['stop_time']
        collected_stats['core.session']['session_time'] = (finishTime
                                                           - startTime)

# Function to send data to the statistics server. Returns True if successful,
# False otherwise.
def send_data(collected_stats):
    rv = api_post(collected_stats, 'collectStats')
    return rv is not None and rv[0] == 200

def update_collected_stats(group, key, value, collected_stats):
    # Top level class can be several times
    group = group.strip()
    if group not in collected_stats:
        collected_stats[group] = {}

    key = key.strip()
    if key.endswith('+'):
        # append value
        key = key.strip('+')
        collected_stats[group].setdefault(key, []).append(value)
    elif key.endswith('&'):
        # accumulate
        key = key.strip('&')
        collected_stats[group].setdefault(key, 0)
        collected_stats[group][key] += value
    elif key.endswith('|'):
        # multiset
        key = key.strip('|')
        collected_stats[group].setdefault(key, {}).setdefault(value, 0)
        collected_stats[group][key][value] += 1
    else:
        collected_stats[group][key] = value

def main():
    log('Starting sender process')
    # get this user's HR data
    user = getuser()
    hashed_idsid = hashlib.sha256(user.encode('utf-8')).hexdigest()
    log(f"User = '{user}', hashed_idsid = '{hashed_idsid}'")

    # dictionary initialization
    collected_stats = {
        'core.session':
        {'session_id': str(uuid4()),
         'python_version': platform.python_version(),
         'python_hexversion': sys.hexversion,
         'clean_exit': False
        },
        'core.environment':
        {'idsid': hashed_idsid,
         'idsid_plain': user,  # Send real user name to web-app for BU lookup

         # We used to send these but now they are calculated from 'idsid_plain'
         # on the server. FIXME: likely, we can just stop sending the fields.
         'business_unit': None,
         'geo_location': None,
        }
    }
    data = sys.stdin.readline()
    # main loop
    while data != '':
        log(f"Got data: {repr(data)}")
        data = data.strip()
        read_dict = json.loads(data)
        group = read_dict['group']
        key = read_dict['key']
        value = read_dict['value']
        # add read values to collected_stats
        update_collected_stats(group, key, value, collected_stats)
        data = sys.stdin.readline()
    log("Done reading data")

    amend_data(collected_stats)
    if debug:
        log(f"Statistics dump: '{collected_stats}'")
    dump_file = os.getenv(ENV_SIMICS_TELEMETRY_DUMP_FILE)
    if dump_file:
        with open(dump_file, "w") as f:
            json.dump(collected_stats, f,
                      # make this debug dump human-readable:
                      indent=4, sort_keys=True)

    if is_send_data:
        log('Sending data')
        succ = send_data(collected_stats)
        log(f'Sending data: {"OK" if succ else "FAILED"}')
    else:
        log('Sending data: SKIPPED')
    log("Exiting...")

if __name__ == '__main__':
    main()
