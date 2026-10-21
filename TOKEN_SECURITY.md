# Mercado Livre token storage

`ml_token_crypto.py` encrypts `conexoes.access_token` and `refresh_token` using authenticated Fernet encryption. The key lives exclusively in the service's `ML_TOKEN_ENCRYPTION_KEY` secret. It is independent of `SECRET_KEY`; session-key changes do not invalidate Mercado Livre credentials. Never log or commit this key. Back up and manage it through the server's secret configuration: losing it requires reconnecting the stores.

## Controlled activation

1. Deploy the compatibility reader with `ML_TOKEN_ENCRYPTION_ENABLED` unset or `0`. No stored credentials are changed. Check the startup configuration log for key presence; it contains no secret values.
2. Provision the key if absent, keep activation at `0`, and redeploy. Verify the new service is live with `key_present=True`; let the previous workers finish draining. All live readers now understand the encrypted format and have the key.
3. Set `ML_TOKEN_ENCRYPTION_ENABLED=1` and redeploy. New connections and refreshes encrypt before writing. A bounded background task migrates up to 50 existing rows per minute, locking rows to serialize with concurrent refreshes. Null credentials remain null. The task is idempotent and retries any plaintext written by a draining compatibility worker.
4. After the prior workers finish draining, verify aggregate counts for both columns: every non-null credential must have the `mlenc:v1:` prefix. Never retrieve the values for verification. Check collector and refresh errors.

The reader supports encrypted and legacy values throughout rollout. Encrypted values require the correct key even when writes are disabled. Corruption or an incorrect/missing key never causes plaintext fallback. Once activated, a missing key prevents application startup.

## Recovery and limits

After migration, roll back only to a revision containing the compatibility reader, preserving the encryption key. Do not roll back to older plaintext-only code. To stop encryption writes temporarily, disable the activation flag while keeping the key; the reader still decrypts existing credentials.

This protects a current database export from revealing credentials without the separate server key. Historical database backups can still contain older plaintext credentials until their retention expires. It does not protect against compromise of the application process together with its secret configuration.
