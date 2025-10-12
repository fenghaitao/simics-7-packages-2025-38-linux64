# © 2016 Intel Corporation

import cli
from . import empty_software_tracker_comp as component
component.empty_software_tracker_comp.register()

def get_empty_software_tracker_status(tracker):
    return [(None, [("Enabled", tracker.enabled)])]

def get_empty_software_tracker_info(tracker):
    return [(None, [("Parent", tracker.parent)])]

def get_empty_software_mapper_status(mapper):
    return [(None, [("Enabled", mapper.enabled)])]

def get_empty_software_mapper_info(mapper):
    return [(None, [("Parent", mapper.parent)])]

tracker_cls = 'empty_software_tracker'
mapper_cls = 'empty_software_mapper'
def add_empty_software_tracker_commands():
    cli.new_info_command(tracker_cls, get_empty_software_tracker_info)
    cli.new_status_command(tracker_cls, get_empty_software_tracker_status)
    cli.new_info_command(mapper_cls, get_empty_software_mapper_info)
    cli.new_status_command(mapper_cls, get_empty_software_mapper_status)

add_empty_software_tracker_commands()
