This change addresses an issue in pluggy that occured when running pytest with any pluggy tracing enabled when parametrized values contained surrogate escape characters.
Before, pluggy attempted to write trace messages using UTF-8 enconding, which fails for lone surrogates. Tracing now encodes lone surrogates with errors="replace" in order
to ensure that trace logging will not crash hook execution in the future.
