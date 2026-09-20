# Router vocabulary

Shared terms for the routing domain. See the [wiki](wiki/index.md) for implementation.

**Client**: The application asking for a completion; Hermes is the client described
by the imported sources.

**Classifier**: The decision-maker that assigns a request to a capability and strength.
It does not produce the requested final answer.

**Solver**: The model that performs the user's requested work after routing.

**Capability**: The work category: GENERAL, REASONING, AGENTIC, or CODING.

**Strength**: The requested level within a capability: EFFICIENT or CAPABLE.

**Tier**: One capability-strength combination, such as CODING_CAPABLE.

**Alias**: A stable client-facing route name whose selected upstream can change.
_Avoid_: Treating an alias as a concrete model identifier.

**Paid sibling**: A paid catalog entry with exactly the free model's base identifier.
A paid route chosen for the same task need not be that model's paid sibling.

**Fallback**: An alternative route attempted after failure of a selected route.

**Quota rewrite**: A route substitution before normal routing when the available
free quota reaches the configured reserve threshold.

**Qualification**: Evidence that a candidate meets a particular probe contract at a
particular time; not a guarantee of general intelligence or ongoing availability.
