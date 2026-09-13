"""Compatibility facade for the pure recovered object semantics.

New code should import from ``game.objects.lifecycle`` or
``game.objects.collection``. Existing boundary adapters, tests and user
scripts may continue importing this module while the semantic package is
organized by object family.
"""

from .game.objects.collection import collection_state, increment_counter
from .game.objects.contact import (contact_decay, contact_path, contact_reaction, contact_reset,
                                   contact_route, contact_repeated_decay, contact_sibling_route,
                                   contact_script_selector)
from .game.objects.lifecycle import (
    activate_collection,
    clear_pair,
    finish_reverse_spawn,
    free_object,
    free_object_reverse,
    initialize,
    relocate_object,
    release_buffer,
    retire_collected_object,
    spawn_collection,
    spawn_region,
    unlink,
)

__all__ = [
    "activate_collection",
    "clear_pair",
    "collection_state",
    "contact_decay",
    "contact_path",
    "contact_reaction",
    "contact_reset",
    "contact_route",
    "contact_repeated_decay",
    "contact_sibling_route",
    "contact_script_selector",
    "finish_reverse_spawn",
    "free_object",
    "free_object_reverse",
    "increment_counter",
    "initialize",
    "relocate_object",
    "release_buffer",
    "retire_collected_object",
    "spawn_collection",
    "spawn_region",
    "unlink",
]
