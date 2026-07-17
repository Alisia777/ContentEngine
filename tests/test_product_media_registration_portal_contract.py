from __future__ import annotations

import base64
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")
RPC_SQL = (ROOT / "supabase" / "migrations" / "202607130004_creator_rpcs.sql").read_text(encoding="utf-8")


def _run_node(source: str) -> dict:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable media contracts"
    result = subprocess.run(
        [node, "--input-type=module", "-"],
        input=source,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_product_media_form_is_explicit_conditional_and_sent_before_upload() -> None:
    section_start = APP.index("function renderMediaSection")
    media_form = APP[APP.index('id="media-upload-form"', section_start):APP.index("function renderFeedbackSection", section_start)]
    submit = APP[APP.index("async function submitMedia(form)"):APP.index("async function track", APP.index("async function submitMedia(form)"))]

    assert 'data-media-product-fields' in media_form
    assert 'name="sku" required maxlength="120"' in media_form
    assert 'name="product_name" required minlength="2" maxlength="180"' in media_form
    assert "function syncMediaProductFields(form)" in APP
    assert 'event.target.name === "kind"' in APP
    assert "mediaKindRequiresProduct(kind)" in submit
    assert "productIdentity.sku = sku" in submit
    assert "productIdentity.product_name = productName" in submit
    assert submit.index("const productIdentity = {}") < submit.index("setFormBusy(form, true")
    assert submit.index("...productIdentity") < submit.index("rights_confirmed")
    assert "removePrivateObject(objectKey)" in submit
    assert "if (form.isConnected) setFormBusy(form, false)" in submit


def test_creator_api_product_identity_guard_is_executable() -> None:
    module_url = "data:text/javascript;base64," + base64.b64encode(API.encode("utf-8")).decode("ascii")
    result = _run_node(
        f'''
globalThis.window = {{ sessionStorage: {{ getItem: () => null, setItem: () => {{}} }} }};
const {{ CreatorApi }} = await import({json.dumps(module_url)});
const calls = [];
const supabase = {{
  schema: () => ({{ rpc: async (name, args) => {{ calls.push({{ name, payload: args.p_payload }}); return {{ data: {{ ok: true }}, error: null }}; }} }}),
}};
const api = new CreatorApi(supabase, {{ RPC_SCHEMA: "public", STORAGE_BUCKET: "contentengine-private" }});
api.organizationId = "00000000-0000-4000-8000-000000000001";
async function capture(input) {{
  try {{ await api.registerMedia(input); return {{ code: "ok" }}; }}
  catch (error) {{ return {{ code: error.code }}; }}
}}
const missingSku = await capture({{ kind: "product_photo", product_name: "Кровавый пилинг" }});
const missingName = await capture({{ kind: "packshot", sku: "WB-1" }});
await api.registerMedia({{ kind: "product_photo", sku: "  WB-159068498  ", product_name: "  Кровавый пилинг  " }});
await api.registerMedia({{ kind: "creator_reference", sku: "must-not-leak", product_name: "must-not-leak" }});
process.stdout.write(JSON.stringify({{ missingSku, missingName, calls }}));
'''
    )

    assert result["missingSku"]["code"] == "media_sku_required"
    assert result["missingName"]["code"] == "media_product_name_required"
    assert len(result["calls"]) == 2
    product_payload = result["calls"][0]["payload"]
    assert product_payload["sku"] == "WB-159068498"
    assert product_payload["product_name"] == "Кровавый пилинг"
    reference_payload = result["calls"][1]["payload"]
    assert "sku" not in reference_payload
    assert "product_name" not in reference_payload


def test_database_remains_the_authoritative_product_media_guard() -> None:
    start = RPC_SQL.casefold().index("create or replace function public.creator_register_media")
    end = RPC_SQL.casefold().index("create or replace function public.creator_capture_event", start)
    body = RPC_SQL[start:end].casefold()

    assert "kind_value in ('product_photo', 'packshot') and product_id_value is null" in body
    assert "require_text(p_payload, 'sku', 1, 120)" in body
    assert "'product_name'," in body and "2," in body and "180" in body
    assert "on conflict on constraint products_org_sku_uq do update" in body