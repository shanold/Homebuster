from pathlib import Path
R=Path(__file__).resolve().parents[1]
base=(R/"movie_catalogue/templates/base.html").read_text()
new=(R/"movie_catalogue/templates/movie_lookup.html").read_text()
api=(R/"movie_catalogue/mobile_api.py").read_text()
kt=(R/"android/app/src/main/java/com/homebuster/mobile/Api.kt").read_text()
main=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
cfg=(R/"movie_catalogue/config.py").read_text()
assert "BarcodeDetector" not in new and "Scan Barcode" not in new
for route in ['@bp.patch("/movies/<int:movie_id>")','@bp.delete("/movies/<int:movie_id>")','@bp.post("/movies/<int:movie_id>/loan")','@bp.post("/movies/<int:movie_id>/return")','@bp.post("/collections")','@bp.delete("/collections/<int:collection_id>")']:
    assert route in api, route
for verb in ['@PATCH("api/v1/movies/{id}")','@DELETE("api/v1/movies/{id}")','@POST("api/v1/movies/{id}/loan")','@POST("api/v1/movies/{id}/return")','@POST("api/v1/collections")']:
    assert verb in kt, verb
for label in ['"Media"','"Collections"','"Loans"','"More"']:
    assert label in main, label
assert "Shelves" in main and "Edit media" in main and "Loan media" in main
assert 'APP_VERSION = "0.3.66"' in cfg
print("v0.3.58 Android client checks: PASS")
