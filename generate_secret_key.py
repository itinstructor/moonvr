import secrets
import os

# Generate a secure random secret key
secret_key = secrets.token_hex(32)

# Save to file
secret_key_path = os.path.join(os.path.dirname(__file__), 'secret_key.txt')

with open(secret_key_path, 'w') as f:
    f.write(secret_key)

print(f"Secret key generated and saved to: {secret_key_path}")
print(f"Key preview: {secret_key[:10]}...")
print("\nIMPORTANT: Add 'secret_key.txt' to .gitignore to prevent committing it!")

