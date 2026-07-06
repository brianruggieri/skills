## Summary
Fixed a null reference error in the parser's `tokenize` function in `tokenizer.ts` where `input.split('')` threw when given null or empty string input. Added an early return guard (`if (!input) return []`) at line 42. Added two test cases to `parser.test.ts` covering empty string and null input. All 10 tests pass. Committed on `fix/null-check-parser`.

## Decisions
None — this session was a straightforward implementation with no contested choices.

## Do Not Retry
None — fix was straightforward with no dead ends.

## Constraints
None beyond what is captured in code and config.

## Next Steps
Task complete — null reference fix committed on `fix/null-check-parser` with passing tests. No follow-up work identified.

## Key Files
- `src/parser/tokenizer.ts` — contains the `tokenize` function where the null guard was added
- `tests/parser.test.ts` — parser test suite with two new empty/null input test cases
