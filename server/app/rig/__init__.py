"""The rig link: protocol, port holder, verdict handler (P2-17).

Three modules, each with one job:

- `protocol` - turn a line into an event and a decision into a line. Pure functions, no state.
- `link` - hold a serial port open, keep it alive, report failures. One small state machine.
- `service` - decide what a trigger means, by asking the quality gate the rest of the product uses.

`wiring` assembles them from settings; `main` starts and stops the assembly with the application.
"""
