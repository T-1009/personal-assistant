"""Generate OpenAPI spec from the FastAPI app."""
import json
from pathlib import Path

# Add project root to path so we can import app
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app

spec = app.openapi()
spec["info"]["version"] = "0.1.0"

output_path = Path(__file__).resolve().parent.parent / "openapi.json"
output_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
print(f"OpenAPI spec written to {output_path}")
