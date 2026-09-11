from pathlib import Path
main = Path("app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
assert "val api = remember(server)" not in main, "Login typing still eagerly constructs Retrofit from partial server text"
assert "ApiFactory.create(current)" in main, "Login should construct Retrofit only after normalization on Sign in"
print("URL regression check passed")
