from pathlib import Path
R=Path(__file__).resolve().parents[1]
api=(R/"movie_catalogue/mobile_api.py").read_text()
kt=(R/"android/app/src/main/java/com/homebuster/mobile/Api.kt").read_text()
main=(R/"android/app/src/main/java/com/homebuster/mobile/MainActivity.kt").read_text()
cfg=(R/"movie_catalogue/config.py").read_text()

for f in ["Blu-ray","Blu-ray + DVD","4K","4K UHD","DVD","HD DVD","VHS","Other"]:
    assert f in main, f
assert 'Text("More Info")' in main
assert 'Text("Loan Media")' in main
assert 'Screen.LOAN_FORM' in main
assert 'Screen.COLLECTION_DETAIL' in main
assert 'Screen.SHELF_DETAIL' in main
assert 'selectedCopy' in main
assert '@GET("api/v1/shelves/{id}/movies")' in kt
assert 'loanedDate' in kt
assert '@bp.get("/shelves/<int:shelf_id>/movies")' in api
assert 'loaned_date = str(data.get("loaned_date")' in api
assert 'APP_VERSION = "0.3.70"' in cfg
assert 'versionName = "0.3.38"' in (R/"android/app/build.gradle.kts").read_text()
assert 'versionCode = 30' in (R/"android/app/build.gradle.kts").read_text()
print("v0.3.59 Android media management checks: PASS")
