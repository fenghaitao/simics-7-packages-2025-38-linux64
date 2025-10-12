# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


'''The update_checkpoint module contains Simics API functions for
writing checkpoint updaters.

See the <cite>Model Builder User's Guide</cite> for more details, in the
<cite>Checkpoint Compatibility</cite> chapter.
'''


__simicsapi_doc_id__ = 'python configuration'

from update_checkpoint_impl import (install_class_configuration_update,
                                    install_generic_configuration_update,
                                    register_update_event_queues,
                                    register_update_nonregistered_class_events,
                                    SIM_register_generic_update,
                                    SIM_register_post_update,
                                    SIM_register_class_update,
                                    all_objects,
                                    for_all_objects,
                                    get_checkpoint_filename,
                                    remove_attr,
                                    rename_attr,
                                    remove_class_attr,
                                    remove_class,
                                    update_configuration,
                                    UpdateException)

# force help() to list all contents
__all__ = sorted(k for k in locals() if not k.startswith('_'))
