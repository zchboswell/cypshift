# EXP-G3 isolated runtime

This additive project contains the exact CPU-only LightGBM 4.7.0 runtime for
the frozen EXP-G3 synthetic gate. It is not part of the installable `cypshift`
package and must not modify the repository-root dependency lock.

The synthetic acceptance driver may use only generated numeric inputs. It has
no official-data compiler, submission path, leaderboard integration, or
model-quality authority.
