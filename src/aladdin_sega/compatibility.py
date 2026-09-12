"""Named, directional loader qualifications. Capture provenance never changes."""
from .profile import PROFILE_SHA256

BASELINE_SOURCE = "baf0418522d9332bcab75b407e0a66c0e41ed10a562ec819a7cd2104e315f40c"
# Filled only for the adapter qualified by the review evidence. A subsequent
# native edit intentionally requires another explicit qualification.
REVIEW_SOURCE = "51a3dab483142fc918862ab4a7dc768e0706ef750bd490acac5a76d08a441d5c"
TRANSITIONS = {"review-baseline-v1": (BASELINE_SOURCE, REVIEW_SOURCE, PROFILE_SHA256)}


def check_source(capture, runtime, *, policy=None):
    if policy is not None and policy not in TRANSITIONS:
        raise ValueError(f"Unknown compatibility transition: {policy}")
    if capture == runtime:
        return
    if policy is not None and TRANSITIONS[policy] == (capture, runtime, PROFILE_SHA256):
        return
    raise ValueError("Capture source identity mismatch; exact reproduction is the default. "
                     "Use the preserved baseline or a specifically qualified --compatibility transition.")
