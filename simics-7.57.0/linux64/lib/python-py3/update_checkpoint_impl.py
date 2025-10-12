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


import sys

from simics import *
import conf
import traceback
import re
import cli
from functools import cmp_to_key
from simicsutils.internal import py3_cmp

# name of Simics Core "module", for updates registered when no module is
# loading
SIMICS_CORE_AS_MODULE = '__simics_core__'

# build-id namespace for Simics and its official packages
SIMICS_BID_NAMESPACE = 'simics'

# List of recently registered update functions that have not yet been sorted
# out by build-id namespace and build-id. Elements are tuples of (module,
# build-id, fun_class)
recently_registered_functions = []

# Dictionary, per build-id namespace, of applicable update functions. Each
# element is a sorted list per build-id, then update function type, of
# applicable functions. Recently registered functions are inserted in the table
# every time a new checkpoint should be updated.
update_functions = {}

# List of generic update functions to apply after the update process has been
# run
post_update_functions = []

class uFunBase:
    def __init__(self, fun):
        self.fun = fun

# Generic update functions:
#
# See documentation for SIM_register_generic_update().
class uFunGeneric(uFunBase):
    pass

def add_config_update_fun(build_id, fun_cls):
    m = CORE_get_current_loading_module()
    recently_registered_functions.append(
        (m if m else SIMICS_CORE_AS_MODULE, build_id, fun_cls))

# kept-for backward compatibility only, use SIM_register_generic_update()
# instead
def install_generic_configuration_update(build_id, function):
    add_config_update_fun(build_id, uFunGeneric(function))

__simicsapi_doc_id__ = 'python configuration'

# register a generic update function in the user update pool
@cli.doc('register a generic update function')
def SIM_register_generic_update(build_id, function):
    '''Register the generic update function <param>function</param> to be run
    when updating a checkpoint to build-id <param>build_id</param>. The
    <param>function</param> acts on one or several objects of various classes,
    and may rename, create or destroy objects. When the checkpoint reaches the
    required build-id, the <param>function</param> will be called once with the
    complete set of objects that constitute the checkpoint as a parameter. It
    is expected to return three lists of pre_conf_objects: (deleted objects,
    changed objects, added objects). Deleted objects must have been removed
    from the configuration, changed objects can have any attribute changed
    (including their class or their name). Added objects must have been added
    to the configuration.

    When renaming an object, the <param>function</param> is expected to remove
    the object from the checkpoint set under its old name and to add it again
    under its new name. The object should be reported in the changed object
    list.'''
    install_generic_configuration_update(build_id, function)

@cli.doc('register a generic update function')
def SIM_register_post_update(function):
    '''Register the generic update function <param>function</param> to be run
    when updating a checkpoint to build-id <param>build_id</param>. after all
    build-id based update functions have run, but before the checkpoint is
    loaded. The <param>function</param> should behave as functions added with
    <fun>SIM_register_generic_update</fun>.'''
    post_update_functions.append(uFunGeneric(function))

# Class update functions:
#
# See documentation for SIM_register_class_update().
class uFunClass(uFunBase):
    def __init__(self, fun, cls):
        uFunBase.__init__(self, fun)
        self.cls = cls

# kept-for backward compatibility only, use SIM_register_class_update()
# instead
def install_class_configuration_update(build_id, classname, function):
    add_config_update_fun(build_id, uFunClass(function, classname))

@cli.doc('register a class update function')
def SIM_register_class_update(build_id, classname, function):
    '''Register the class update function <param>function</param> for class
    <param>classname</param>, to be run when updating a checkpoint to build-id
    <param>build_id</param>.

    The <param>function</param> acts on a single object of a given class. It
    will be called for all matching objects with the current object as
    argument. It doesn't need to return anything, however it can't create or
    destroy objects, only change the attributes of the object it got as
    parameter, except the object name.'''
    install_class_configuration_update(build_id, classname, function)

# Exception raised when the update process can not be performed
class UpdateException(Exception):
    pass

# class used to intercept pre conf object modifications
class _ChangeMonitor:
    def __init__(self):
        self.mods = []
    def object_added(self, o):
        self.mods.append(('add', o.name, o, None))
    def object_removed(self, o):
        self.mods.append(('remove', o.name, o, None))
    def classname_changed(self, o, old_classname, new_classname):
        self.mods.append(('classchange', o.name, o,
                          (old_classname, new_classname)))

# Cache for object to class and class to object relations
class Cache:
    def __init__(self, checkpoint):
        # ensure that child objects are included in the checkpoint dictionary
        def add_missing_children(o):
            for child in o._o:
                if child.name not in checkpoint:
                    checkpoint[child.name] = child
                    add_missing_children(child)
        for o in list(checkpoint.values()):
            add_missing_children(o)

        # add parent/child relations
        pre_conf_object._linkup(checkpoint)

        # set of objects for a given class
        o_from_c = {}
        for o in checkpoint.values():
            o_from_c.setdefault(o.__class_name__, set()).add(o)

        self.checkpoint = checkpoint
        self.o_from_c = o_from_c
        self.updated_bid_namespaces = set()
        self.monitor = _ChangeMonitor()

    def objects_from_class(self, c):
        """Return the set of objects of class 'c'"""
        if c in self.o_from_c:
            return self.o_from_c[c]
        else:
            return set()
    def all_objects_by_class(self):
        """Return a list of (classname, object_set) tuples"""
        return self.o_from_c.items()
    def remove_object(self, o):
        """Update the cache when an object is removed from the checkpoint"""
        o._unlink()
        o._change_monitor = None
        self.monitor.object_removed(o)

    def add_object(self, o):
        """Update the cache when an object is added to the checkpoint"""
        # Attach to parent, if available.
        o._change_monitor = self.monitor
        if not o._parent:
            p = self.checkpoint.get(o._parent_name, None)
            if p is not None:
                p |= o
        self.monitor.object_added(o)

    def classname_changed(self, o, old_classname, new_classname):
        """Update the cache when an object changes class"""
        self.monitor.classname_changed(o, old_classname, new_classname)

    def add_namespace(self, ns):
        self.updated_bid_namespaces.add(ns)
    def namespace_updated(self, ns):
        return ns in self.updated_bid_namespaces

    # install change monitor hook
    def __enter__(self):
        # monitor used to keep track of changes
        for o in self.checkpoint.values():
            o._change_monitor = self.monitor

    # remove change monitor hook
    def __exit__(self, e_type, e_val, traceback):
        for o in self.checkpoint.values():
            o._change_monitor = None

    # Apply object changes to the cache. The update is delayed to avoid
    # problems with iterators.
    def update(self):
        mods = self.monitor.mods
        if not mods:
            return ()
        self.monitor.mods = []

        validate = set()
        for (cmd, name, o, extra) in mods:
            if cmd == 'add':
                validate.add(name)
                self.checkpoint[name] = o
                self.o_from_c.setdefault(o.classname, set()).add(o)

            elif cmd == 'remove':
                # ...detach from parent
                if name in self.checkpoint:
                    del self.checkpoint[name]
                self.o_from_c[o.classname].discard(o)
                validate.discard(name)

            elif cmd == 'classchange':
                (old_class, new_class) = extra
                self.o_from_c[old_class].discard(o)
                self.o_from_c.setdefault(new_class, set()).add(o)
                validate.add(name)
        self.mods = []
        return list(validate)

    # validate that added/modified objects belongs to correct namespace etc
    # and that added objects have build_id set properly
    def update_and_validate(self, classes, bid_ns, bid, fun):
        validate = self.update()
        for name in validate:
            o = self.checkpoint[name]
            fill_in_build_id(bid_ns, bid, o, fun, classes)
            check_for_namespace_mismatch(o, classes, bid_ns, self, fun)


# The file name of the checkpoint being updated. (Ideally it should
# not be a global but passed to update functions, but that would
# entail signature changes and destroy compatibility.)
checkpoint_filename = None

def set_checkpoint_filename(filename):
    global checkpoint_filename
    checkpoint_filename = filename

def get_checkpoint_filename():
    """The file name of the checkpoint being updated."""
    return checkpoint_filename

# Update a checkpoint. filename is where it came from (the bundle
# directory, or the config file itself for pre-bundle checkpoints).
def update_configuration(checkpoint, filename):
    set_checkpoint_filename(filename)
    try:
        perform_update_configuration(checkpoint)
    except UpdateException:
        if SIM_get_verbose():
            traceback.print_exc(file = sys.stdout)
        raise
    except Exception:
        if SIM_get_verbose():
            traceback.print_exc(file = sys.stdout)
        raise
    finally:
        set_checkpoint_filename(None)

def print_verbose(string):
    if SIM_get_verbose():
        print("[Update Checkpoint]", string)

# sort update functions by build-id first, then update type (generic before
# class)
def sort_updates(ta, tb):
    ba, fa = ta # build-id, update function
    bb, fb = tb
    return py3_cmp((ba, 0 if isinstance(fa, uFunGeneric) else 1),
                   (bb, 0 if isinstance(fb, uFunGeneric) else 1))

# sort build-id namespace so that SIMICS_BID_NAMESPACE always comes last
def sort_bid_ns(na, nb):
    if na == SIMICS_BID_NAMESPACE:
        return -1
    elif nb == SIMICS_BID_NAMESPACE:
        return 1
    else:
        return py3_cmp(na, nb)

# module description for update purposes
class module_desc:
    def __init__(self, module, bid_ns, bid, bdate=0, user_path=False):
        self.name = module
        self.build_id_namespace = bid_ns
        self.build_id = bid
        self.build_date = bdate
        self.user_path = user_path

# class description for update purposes
class class_desc:
    def __init__(self, cls, bid_ns, bid):
        self.name = cls
        self.build_id_namespace = bid_ns
        self.build_id = bid

# merge the recently registered update functions in 'new_functions' into
# 'current_set', using the 'all_modules' dictionary containing a list of all
# modules, then resort the lists in 'current_set'
def merge_new_update_functions(current_set, new_functions, all_modules):
    lists_to_sort = set()
    for module, build_id, f in new_functions:
        m = all_modules[module]
        if m.build_id_namespace == '__simics_project__':
            raise UpdateException(
                "The update function %s has been defined by the module '%s', "
                "but it is compiled without valid build-id." % (
                    repr(f.fun), m.name))
        if not m.build_id_namespace in current_set:
            current_set[m.build_id_namespace] = []
        current_set[m.build_id_namespace].append((build_id, f))
        lists_to_sort.add(m.build_id_namespace)
    for ns in lists_to_sort:
        current_set[ns] = sorted(current_set[ns],
                                 key = cmp_to_key(sort_updates))

def module_precedes(m1, m2):
    # Resolve duplicate modules using the same precedence rules as implemented
    # by module_precedes() in modules.c. Any changes made here should also be
    # reflected in modules.c.

    assert isinstance(m1, module_desc) and isinstance(m2, module_desc)

    # User modules take precedence
    if m1.user_path != m2.user_path:
        return m1.user_path

    # Newer modules take precedence
    if m1.build_date != m2.build_date:
        return m1.build_date > m2.build_date

    # Use alphabetic order otherwise
    return m1.name < m2.name

def perform_update_configuration(checkpoint):

    # check if we have a checkpoint to update at all
    try:
        sim_version = checkpoint['sim'].version
    except (AttributeError, KeyError):
        # This is a configuration, not a checkpoint. Do nothing.
        return

    if sim_version < SIM_VERSION_6:
        raise cli.CliError("Checkpoint too old. Simics does not support"
                           " loading checkpoints from versions before 6. Try"
                           " loading the checkpoint in Simics 6 and save it.")

    modules = {}                # dict (module) -> (module_desc)
    classes = {}                # dict (class) -> (class_desc)
    ctom = {}                   # dict (class) -> (module)

    # build the dictionaries of module and class descriptions
    for m in SIM_get_all_modules():
        # SIM_get_all_modules() can grow over time
        name = m[0]
        build_id = m[5]
        build_date = m[6]
        cls = m[7]
        user_path = m[10]
        # see SIMICS-10153
        bid_ns = CORE_get_extra_module_info(name)[0]
        modules[name] = module_desc(name, bid_ns, build_id,
                                    build_date, user_path)
        for c in cls:
            if (c not in classes
                or module_precedes(modules[name], modules[ctom[c]])):
                classes[c] = class_desc(c, bid_ns, build_id)
                ctom[c] = name

    # add Simics Core itself as a module
    modules[SIMICS_CORE_AS_MODULE] = module_desc(SIMICS_CORE_AS_MODULE,
                                                 SIMICS_BID_NAMESPACE,
                                                 conf.sim.build_id)

    # add recently added update functions to the main set
    merge_new_update_functions(update_functions, recently_registered_functions,
                               modules)

    # prepare indexed data structures for faster accesses
    cache = Cache(checkpoint)

    for (classname, _) in cache.all_objects_by_class():
        if classname not in classes:
            # the class is not provided by any of the module we know
            # about. There can be several reasons:
            # 1. the class belongs to Simics core
            # 2. the class belongs to a module that is not installed, so loading
            #    the checkpoint will fail
            # 3. the class doesn't exist anymore, and a checkpoint updater will
            #    remove the corresponding objects
            # Since we don't know and it has no consequence on the way the
            # checkpoint updating will succeed or fail, we assume 1.
            classes[classname] = class_desc(classname,
                                            SIMICS_BID_NAMESPACE,
                                            conf.sim.build_id)

    # Loop over all checkpoint set objects and set those without build-ids
    # to the version reported by the sim object in the checkpoint.
    # Do sanity checks: all objects of the same class should have the same
    # build_id, and this build_id should be smaller or equal to the current
    # build_id for the class. At the same time, build a list of oldest build-id
    # for each build-id namespace, indexed by namespace name
    oldest_build_ids = {}       # dict (bid_ns) -> (oldest build-id)
    too_new_dict = {}           # dict (too_new_bid, bid) -> module
    for (classname, object_set) in cache.all_objects_by_class():
        build_id = None
        for o in object_set:
            if not hasattr(o, "build_id"):
                print_verbose("Patching object %s to 'sim' version %d" % (
                    o.name, sim_version))
                o.build_id = sim_version
            if build_id is None:
                build_id = o.build_id
            elif build_id != o.build_id:
                raise UpdateException(
                    "Several objects of class %s do "
                    "not have the same build-id." % classname)
        cls_build_id = classes[classname].build_id
        if cls_build_id < build_id:
            if (build_id, cls_build_id) in too_new_dict:
                too_new_dict[(build_id, cls_build_id)].append(classname)
            else:
                too_new_dict[(build_id, cls_build_id)] = [classname]

        bid_ns = classes[classname].build_id_namespace
        if not bid_ns in oldest_build_ids or build_id < oldest_build_ids[bid_ns]:
            oldest_build_ids[bid_ns] = build_id

    for ns in oldest_build_ids:
        print_verbose("-> found namespace '%s' with oldest build-id %d"
                      % (ns, oldest_build_ids[ns]))

    if too_new_dict:
        print('Warning: checkpoint produced with a newer Simics version')
        if not SIM_get_verbose():
            print('Run with -verbose to get a list of too old classes')
        else:
            for (bid, cbid) in too_new_dict:
                print('Build-id in checkpoint: %d, current: %d' % (bid, cbid))
                for cls in too_new_dict[(bid, cbid)]:
                    print(cls)

    with cache:
        # loop over all build-id namespaces and call
        # the relevant update functions
        build_id_namespaces = sorted(update_functions.keys(),
                                     key = cmp_to_key(sort_bid_ns))
        for ns in build_id_namespaces:
            if ns in oldest_build_ids:
                apply_update_list(checkpoint, classes, cache,
                                  ns, oldest_build_ids[ns],
                                  update_functions[ns])
            else:
                # nothing to do, since no object belong
                # to this build-id namespace
                pass
            cache.add_namespace(ns)

        # apply the generic post-update functions
        apply_post_update_list(checkpoint, classes, cache,
                               post_update_functions)


# check that a given object 'obj', assumed to have been created or modified,
# doesn't belong to a build-id namespace that has already been updated. If it
# does, complain that the object won't be able to be updated.
def check_for_namespace_mismatch(obj, classes, ns, cache, update_fun):
    if obj.__class_name__ in classes:
        cls_bid_ns = classes[obj.__class_name__].build_id_namespace
        if cache.namespace_updated(cls_bid_ns):
            update_fun_name = (("A generic update function '%s'" % repr(update_fun.fun))
                               if isinstance(update_fun, uFunGeneric)
                               else ("A class update function '%s' for class '%s'"
                                     % (repr(update_fun.fun), update_fun.cls)))
            raise UpdateException(
                "%s"
                " has created or modified the object '%s' of class '%s' but "
                "this class should already have been updated "
                "(it belongs to the build-id namespace '%s' whereas "
                "the current namespace is '%s')" % (
                        update_fun_name, obj.name,
                        obj.__class_name__, cls_bid_ns, ns))

def fill_in_build_id(bid_ns, bid, obj, update_fun, classes):
    print_verbose("-> check that '%s' has valid build-id" % obj.name)
    if hasattr(obj, "build_id"):
        print_verbose("   -> found build-id %d" % obj.build_id)
        return
    if obj.__class_name__ in classes:
        cls_bid_ns = classes[obj.__class_name__].build_id_namespace
        if cls_bid_ns != bid_ns:
            raise UpdateException(
                "A generic update function '%s' has created the object '%s' of "
                "class '%s' without giving it an explicit build-id. "
                "However, this class belongs to the build-id namespace '%s' "
                "whereas the current namespace is '%s', so Simics can not "
                "guess what build-id the new object should have for update "
                "purposes." % (
                    repr(update_fun.fun), obj.name,
                    obj.__class_name__, cls_bid_ns, bid_ns))

    print_verbose("  -> setting build-id %d for object %s" %
                  (bid, obj.name))
    obj.build_id = bid

def apply_update_list(checkpoint, classes, cache, bid_ns, oldest_build_id,
                      update_functions):

    # loop over the active build-ids to update all objects
    for build_id, fun in update_functions:
        if build_id <= oldest_build_id:
            continue

        if isinstance(fun, uFunGeneric):
            print_verbose("build-id %d: apply generic function %s" %
                          (build_id, repr(fun.fun)))
            apply_generic_update_function(checkpoint, cache, fun)
            cache.update_and_validate(classes, bid_ns, build_id, fun)
        else:
            if fun.cls in classes:
                # check that we don't apply a class function from the 'future'
                if classes[fun.cls].build_id < build_id:
                    raise UpdateException(
                        "The class %s has registered an upgrade function "
                        "for a higher build-id than it currently has "
                        "(%d < %d)." % (fun.cls,
                                        classes[fun.cls].build_id,
                                        build_id))
            # apply the function on all related objects
            for obj in list(cache.objects_from_class(fun.cls)):
                if obj.build_id < build_id:
                    print_verbose("build-id %d, class %s: apply function %s" %
                                  (build_id, fun.cls, repr(fun.fun)))
                    fun.fun(obj)
                    cache.update_and_validate(classes, bid_ns, build_id, fun)
                else:
                    print_verbose("build-id %d, class %s: skip function %s "
                                  "since class build-id is %d" %
                                  (build_id, fun.cls, repr(fun.fun),
                                   obj.build_id))

def apply_post_update_list(checkpoint, classes, cache, update_functions):
    for update_fun in update_functions:
        apply_generic_update_function(checkpoint, cache, update_fun)
        cache.update()

def apply_generic_update_function(checkpoint, cache, update_fun):
    (deleted_objects,
     changed_objects,
     added_objects) = update_fun.fun(checkpoint)

    # Remove deleted objects
    for obj in deleted_objects:
        print_verbose("-> check that object %s was deleted" % obj.name)
        # check that the objects are not present anymore
        if obj.name in checkpoint:
            raise UpdateException(
                "A generic update function (%s)"
                " claims it removed the object '%s' of class '%s' but "
                "didn't." % (repr(update_fun.fun), obj.name,
                             obj.__class_name__))
        cache.remove_object(obj)

    # add added objects
    for obj in added_objects:
        print_verbose("-> check that object %s was added" % obj.name)
        if not obj.name in checkpoint:
            raise UpdateException(
                "A generic update function (%s)"
                " claims it added the object '%s' of class '%s' but "
                "didn't." % (repr(update_fun.fun), obj.name,
                             obj.__class_name__))
        cache.add_object(obj)

# Specific updates

# Specify f as a filter for all cpu events (both step and time) for
# builds preceding build_id. If f returns None, the event is discarded.
def register_update_event_queues(build_id, f):
    def update(conf):
        changed = []
        for o in list(conf.values()):
            if hasattr(o, "time_queue"):
                o.time_queue = [e for e in map(f, o.time_queue) if e]
                if o not in changed:
                    changed.append(o)

            if hasattr(o, "step_queue"):
                o.step_queue = [e for e in map(f, o.step_queue) if e]
                if o not in changed:
                    changed.append(o)

        return ([], changed, [])

    install_generic_configuration_update(build_id, update)

#
# Register an event update functions for nonregistered events for the class classname,
# where build_id is the build_id for which we should apply function f.
# f should take the data for an unregistered event and return an event class name and the
# associated data.
#
def register_update_nonregistered_class_events(build_id, classname, f):
    def event_trans(ev):
        (sim, name, load, slot, time) = ev
        if name == "(nonregistered)" or name == "(nonregistered machine_sync)":
            (obj, data) = load
            if sim.name == "sim" and re.match(classname, obj.classname):
                (new_name, new_data) = f(data)
                return [obj, new_name, new_data, slot, time]
        elif (name == "Machine Sync Event (early)"
              or name == "Machine Sync Event"
              or name == "Machine Sync Event (late)"):
            (wrap_sim, wrap_class, wrap_name, wrap_load) = load
            if (wrap_name == "(nonregistered)"
                or wrap_name == "(nonregistered machine_sync)"):
                (wrap_obj, wrap_data) = wrap_load
                if wrap_sim.name == "sim" and re.match(classname, wrap_obj.classname):
                    (new_wrap_name, new_wrap_data) = f(wrap_data)
                    return [sim, name,
                            [wrap_obj, classname,
                             new_wrap_name, new_wrap_data],
                            slot, time]
        return ev

    register_update_event_queues(build_id, event_trans)

@cli.doc('return all objects of a given class',
         module = 'update_checkpoint')
def all_objects(set, classname):
    '''This function should only be used while updating checkpoints, as
    described in <cite>Model Builder User's Guide</cite>, in the
    <cite>Checkpoint Compatibility</cite> chapter.

    Return a list of all objects of class <param>classname</param> present in
    the checkpoint <param>set</param>.'''
    return [x for x in list(set.values()) if x.classname == classname]

@cli.doc('apply a function on all objects of a given class',
         module = 'update_checkpoint')
def for_all_objects(set, classname, function):
    '''This function should only be used while updating checkpoints, as
    described in <cite>Model Builder User's Guide</cite>, in the
    <cite>Checkpoint Compatibility</cite> chapter.

    Apply the function <param>function</param> on all objects of class
    <param>classname</param> present in <param>set</param>.
    <param>function</param> is defined as:

    <pre>function(config, object)</pre>

    where <param>config</param> is the Python dictionary containing all
    objects, and object is an object of class <param>classname</param>.'''

    for obj in all_objects(set, classname):
        function(set, obj)

@cli.doc('remove an attribute',
         module = 'update_checkpoint')
def remove_attr(obj, name):
    '''This function should only be used while updating checkpoints, as
    described in <cite>Model Builder User's Guide</cite>, in the
    <cite>Checkpoint Compatibility</cite> chapter.

    Remove the attribute <param>name</param> from the object
    <param>obj</param>.'''
    try:
        delattr(obj, name)
    except AttributeError:
        pass

@cli.doc('rename an attribute',
         module = 'update_checkpoint')
def rename_attr(obj, new_attr, old_attr):
    '''This function should only be used while updating checkpoints, as
    described in <cite>Model Builder User's Guide</cite>, in the
    <cite>Checkpoint Compatibility</cite> chapter.

    Rename the attribute <param>old_attr</param> to <param>new_attr</param> in
    the object <param>obj</param>.'''
    try:
        setattr(obj, new_attr, getattr(obj, old_attr))
    except AttributeError:
        pass
    remove_attr(obj, old_attr)

@cli.doc('remove a class attribute',
         module = 'update_checkpoint')
def remove_class_attr(set, classname, name):
    '''This function should only be used while updating checkpoints, as
    described in <cite>Model Builder User's Guide</cite>, in the
    <cite>Checkpoint Compatibility</cite> chapter.

    In the checkpoint <param>set</param>, remove the class attribute
    <param>name</param> from all objects of class <param>classname</param>.'''
    for obj in all_objects(set, classname):
        remove_attr(obj, name)

@cli.doc('remove all instances of a class',
         module = 'update_checkpoint')
def remove_class(set, classname):
    '''This function should only be used while updating checkpoints, as
    described in <cite>Model Builder User's Guide</cite>, in the
    <cite>Checkpoint Compatibility</cite> chapter.

    In the checkpoint <param>set</param>, remove all objects of class
    <param>classname</param>.'''
    for obj in all_objects(set, classname):
        del set[obj.name]
