# BRVM Package TODO

## Current Status
- [x] Fundamentals data available (PER, PBR, ROE, ROA in DB/CSV)
- [x] Fix import errors
  - api/__init__.py syntax
  - objects/__init__.py relative imports
- [x] Full validation (tests ✓17/17, CLI all OK, import OK)
- [ ] Add screener polish, portfolio optimize
- [ ] Live robustness (timeouts OK, sync works)

  - api/__init__.py syntax
  - objects/__init__.py relative imports
- [ ] Restructure to simpler brvm/ if needed (current good)
- [ ] Full validation (tests, CLI, sync)
- [ ] Add screener, portfolio optimize (partial)
- [ ] Live robustness (timeouts, logs)
- [ ] yfinance-like API (Ticker.history etc - partial)

## Next
1. Fix imports
2. Run validate_package
3. Test Ticker('SNTS').info()

