"""
Enumeration modules are the core information gathering mechanism within
pwncat. Enumeration modules are a subclass of :class:`pwncat.modules.BaseModule`.
However, they extend the functionality of a module to cache results
within the database and provide a structured way of specifying how often
to execute a given enumeration.

An enumeration module returns a list of facts. Each fact must inherit from
:class:`pwncat.db.Fact`. Each fact that is generated is stored in the
database, and deduplicated. A fact can have one or more types. A type is
simply a string which identifies the kind of data the fact represents.
When you define an enumeration module, you must specify a list of fact
types which your module is capable of generating. This is so that pwncat
can automatically locate facts of any type. Further, you must specify the
"schedule" for your enumeration. Schedules identify whether a module should
run only once, once per user or should run every time the given type is
requested. Unlike base modules, enumeration modules do not accept any
custom arguments. However, they do still require a list of compatible
platforms.

When defining an enumeration module, you must define the
:func:`EnumerateModule.enumerate` method. This method is a generator which
can yield either facts or status updates, just like the
:func:`pwncat.modules.BaseModule.run` method.

Example Enumerate Module
------------------------

.. code-block:: python
    :caption: Example Enumerate Module

    class CustomFact(Fact):
        \""" Custom fact data regarding the target \"""

        def __init__(self, source):
            super().__init__(source=source, types=["custom.fact.type"])

        def title(self, session: "pwncat.manager.Session"):
            return "[red]Custom Fact![/red]"

    class Module(EnumerateModule):
        \""" Module documentation \"""

        PLATFORM = [Windows]
        SCHEDULE = Schedule.PER_USER
        PROVIDES = ["custom.fact.type"]

        def enumerate(self, session: "pwncat.manager.Session"):
            yield CustomFactObject(self.name)

"""
import time
import typing
import fnmatch
from enum import Enum, auto

import persistent

import pwncat
from pwncat.db import Fact
from pwncat.modules import List, Status, Argument, BaseModule
from pwncat.platform import Platform
from pwncat.platform.linux import Linux


class Schedule(Enum):
    """Defines how often an enumeration module will run"""

    ALWAYS = auto()
    """ Execute the enumeration every time the module is executed """
    PER_USER = auto()
    """ Execute the enumeration once per user on the target """
    ONCE = auto()
    """ Execute the enumeration once and only once """


class EnumerateModule(BaseModule):
    """Base class for all enumeration modules.

    As discussed above, an enumeration module must define the :func:`enumerate`
    method, provide a list of supported platforms, a list of provided fact types
    and a schedule.

    The base enumeration module's :func:`run` method will provide a few routines
    and options. You can filter the results of this module with the ``types``
    argument. This causes the module to only return the types specified. You can
    also tell the module to clear any cached data from the database generated by
    this module. Lastly, if you specify ``cache=False``, the module will only
    return new facts that were not cached in the database already.
    """

    # List of categories/enumeration types this module provides
    # This should be set by the sub-classes to know where to find
    # different types of enumeration data
    PROVIDES: typing.List[str] = []
    """ List of fact types which this module is capable of providing """
    PLATFORM: typing.List[typing.Type[Platform]] = []
    """ List of supported platforms for this module """

    SCHEDULE: Schedule = Schedule.ONCE
    """ Determine the run schedule for this enumeration module """

    # Arguments which all enumeration modules should take
    # This shouldn't be modified. Enumeration modules don't take any
    # parameters
    ARGUMENTS = {
        "types": Argument(
            List(str),
            default=[],
            help="A list of enumeration types to retrieve (default: all)",
        ),
        "clear": Argument(
            bool,
            default=False,
            help="If specified, do not perform enumeration. Cleared cached results.",
        ),
        "cache": Argument(
            bool,
            default=True,
            help="return cached facts along with new facts (default: True)",
        ),
    }
    """ Arguments accepted by all enumeration modules. This **should not** be overridden. """

    def run(
        self,
        session: "pwncat.manager.Session",
        types: typing.List[str],
        clear: bool,
        cache: bool,
    ):
        """Locate all facts this module provides.

        Sub-classes should not override this method. Instead, use the
        enumerate method. `run` will cross-reference with database and
        ensure enumeration modules aren't re-run.

        :param session: the session on which to run the module
        :type session: pwncat.manager.Session
        :param types: list of requested fact types
        :type types: List[str]
        :param clear: whether to clear all cached enumeration data
        :type clear: bool
        :param cache: whether to return facts from the database or only new facts
        :type cache: bool
        """

        # Retrieve the DB target object
        target = session.target

        if clear:
            # Filter out all facts which were generated by this module
            target.facts = persistent.list.PersistentList(
                (f for f in target.facts if f.source != self.name)
            )

            # Remove the enumeration state if available
            if self.name in target.enumerate_state:
                del target.enumerate_state[self.name]

            return

        # Yield all the know facts which have already been enumerated
        if cache and types:
            yield from (
                f
                for f in target.facts
                if f.source == self.name
                and any(
                    any(fnmatch.fnmatch(item_type, req_type) for req_type in types)
                    for item_type in f.types
                )
            )
        elif cache:
            yield from (f for f in target.facts if f.source == self.name)

        # Check if the module is scheduled to run now
        if (self.name in target.enumerate_state) and (
            (self.SCHEDULE == Schedule.ONCE and self.name in target.enumerate_state)
            or (
                self.SCHEDULE == Schedule.PER_USER
                and session.platform.getuid() in target.enumerate_state[self.name]
            )
        ):
            return

        for item in self.enumerate(session):

            # Allow non-fact status updates
            if isinstance(item, Status):
                yield item
                continue

            # Only add the item if it doesn't exist
            for f in target.facts:
                if f == item:
                    yield Status(item.title(session))
                    break
            else:
                target.facts.append(item)

                # Don't yield the actual fact if we didn't ask for this type
                if not types or any(
                    any(fnmatch.fnmatch(item_type, req_type) for req_type in types)
                    for item_type in item.types
                ):
                    yield item
                else:
                    yield Status(item.title(session))

        # Update state for restricted modules
        if self.SCHEDULE == Schedule.ONCE:
            target.enumerate_state[self.name] = True
        elif self.SCHEDULE == Schedule.PER_USER:
            if not self.name in target.enumerate_state:
                target.enumerate_state[self.name] = persistent.list.PersistentList()
            target.enumerate_state[self.name].append(session.platform.getuid())

    def enumerate(
        self, session: "pwncat.manager.Session"
    ) -> typing.Generator[Fact, None, None]:
        """Enumerate facts according to the types listed in ``PROVIDES``.

        :param session: the session on which to enumerate
        :type session: pwncat.manager.Session
        """
