from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web/app/generation-strategy-assets.js"
SOURCE = MODULE.read_text(encoding="utf-8")
API_SOURCE = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation strategy asset contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "assets.mjs").write_text(SOURCE, encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import * as subject from './assets.mjs';\n"
            "const ids = Object.freeze({\n"
            " project:'11111111-1111-4111-8111-111111111111',\n"
            " source:'22222222-2222-4222-8222-222222222222',\n"
            " productMedia:'33333333-3333-4333-8333-333333333333',\n"
            " product:'44444444-4444-4444-8444-444444444444',\n"
            "});\n"
            "const cursor=(id,at)=>({at,id});\n"
            "const source=(duration=8.125)=>({\n"
            " id:ids.source,kind:'source_video',mime_type:'video/mp4',\n"
            " duration_seconds:duration,status:'ready',rights_confirmed:true,\n"
            " product_id:null,product_identity:null,filename:'source.mp4',\n"
            " exact_youtube_attached:true,eligible_roles:['source_video'],\n"
            " eligible_strategy_roles:[\n"
            "  {strategy_id:'viral_avatar_ugc',role:'source_video'},\n"
            "  {strategy_id:'viral_rebuild',role:'source_video'},\n"
            "  ...(duration===null?[]:[{strategy_id:'viral_product_swap',role:'source_video'}]),\n"
            " ],eligible:true,blocking_codes:[],blocking_codes_by_strategy:{\n"
            "  viral_avatar_ugc:[],\n"
            "  viral_product_swap:duration===null?['server_duration_probe_required']:[],\n"
            "  viral_rebuild:[],\n"
            " },created_at:'2026-08-14T08:00:00.000Z',\n"
            " _cursor:cursor(ids.source,'2026-08-14T08:00:00.000Z'),\n"
            "});\n"
            "const product=()=>({\n"
            " id:ids.productMedia,kind:'product_photo',mime_type:'image/png',\n"
            " duration_seconds:null,status:'ready',rights_confirmed:true,\n"
            " product_id:ids.product,product_identity:{product_id:ids.product,\n"
            "  sku:'SKU-1',product_name:'Exact product',identity_verified:true},\n"
            " filename:'product.png',exact_youtube_attached:false,\n"
            " eligible_roles:['product_image','new_product_image'],\n"
            " eligible_strategy_roles:[\n"
            # У «Дуэта» товарной роли нет вовсе: он комментирует чужой ролик,
            # а не показывает товар. Фотография остаётся годной для «Копии» и
            # «Создания», а для дуэта названа неподходящей — запись остаётся в
            # выдаче с причиной, а не исчезает из неё молча.
            "  {strategy_id:'viral_product_swap',role:'new_product_image'},\n"
            "  {strategy_id:'viral_rebuild',role:'product_image'},\n"
            " ],eligible:true,blocking_codes:[],blocking_codes_by_strategy:{\n"
            "  viral_avatar_ugc:['strategy_role_unavailable'],\n"
            "  viral_product_swap:[],viral_rebuild:[],\n"
            " },created_at:'2026-08-14T07:00:00.000Z',\n"
            " _cursor:cursor(ids.productMedia,'2026-08-14T07:00:00.000Z'),\n"
            "});\n"
            "const response=(assets=[source(),product()],overrides={})=>({\n"
            " ok:true,version:'generation-strategy-asset-candidates-response-v1',\n"
            " project_id:ids.project,assets,_meta:{page_size:50,has_more:false,\n"
            " next_cursor:null,kind:'all',product_id:null,\n"
            " cursor_mode:'keyset_created_at_id'},contract:{read_only:true,\n"
            " object_names_returned:false,hashes_returned:false,\n"
            " signed_urls_returned:false,\n"
            " source_video_requires_exact_youtube_attachment:true},...overrides,\n"
            "});\n"
            f"const result = {expression};\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_module_is_pure_and_never_accepts_browser_storage_authority() -> None:
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "document.",
        "window.",
        "localStorage",
        "sessionStorage",
        "metadata.duration_seconds",
    ):
        assert forbidden not in SOURCE
    for forbidden_field in ("object_name", "signed_url", "sha256"):
        assert re.search(
            rf"(?:\.|\[\s*['\"]){forbidden_field}(?![a-z0-9_])",
            SOURCE,
        ) is None


def test_browser_transport_uses_one_scoped_read_rpc_with_keyset_pagination() -> None:
    assert (
        'generationStrategyAssetCandidates:\n'
        '    "creator_generation_strategy_asset_candidates"'
    ) in API_SOURCE
    section = API_SOURCE[
        API_SOURCE.index("  generationStrategyAssetCandidates(options = {}) {") :
        API_SOURCE.index("  archiveGenerationBatch(batchId, options = {}) {")
    ]
    for marker in (
        'version: "generation-strategy-asset-candidates-request-v1"',
        "project_id: projectId",
        "page_size: pageSize",
        "...(productId ? { product_id: productId } : {})",
        "payload.cursor = { at: cursorAt, id: cursorId }",
        "RPC.generationStrategyAssetCandidates",
        "this.withOrganization(payload)",
    ):
        assert marker in section
    for forbidden in (
        "invokeRealGeneration",
        "actor_id",
        "object_name",
        "signed_url",
        "sha256",
        "duration_seconds",
    ):
        assert forbidden not in section


def test_exact_server_page_normalizes_and_freezes_safe_facts() -> None:
    result = _evaluate(
        """
        (()=>{
          const normalized=subject.normalizeGenerationStrategyAssetCandidates(
            response(),{projectId:ids.project,kind:'all',productId:null});
          return {ok:normalized.ok,frozen:Object.isFrozen(normalized.page.assets[0]),
            duration:normalized.page.assets[0].duration_seconds,
            product:normalized.page.assets[1].product_identity,
            contract:normalized.page.contract};
        })()
        """
    )
    assert result == {
        "ok": True,
        "frozen": True,
        "duration": 8.125,
        "product": {
            "product_id": "44444444-4444-4444-8444-444444444444",
            "sku": "SKU-1",
            "product_name": "Exact product",
            "identity_verified": True,
        },
        "contract": {
            "read_only": True,
            "object_names_returned": False,
            "hashes_returned": False,
            "signed_urls_returned": False,
            "source_video_requires_exact_youtube_attachment": True,
        },
    }


def test_swap_requires_server_duration_but_other_reference_modes_remain_eligible() -> None:
    result = _evaluate(
        """
        (()=>{
          const normalized=subject.normalizeGenerationStrategyAssetCandidates(
            response([source(null)]),{projectId:ids.project});
          const asset=normalized.page.assets[0];
          return {
            normalized:normalized.ok,
            swap:subject.generationStrategyAssetEligibility(
              asset,'viral_product_swap','source_video'),
            ugc:subject.generationStrategyAssetEligibility(
              asset,'viral_avatar_ugc','source_video'),
            rebuild:subject.generationStrategyAssetEligibility(
              asset,'viral_rebuild','source_video'),
          };
        })()
        """
    )
    assert result == {
        "normalized": True,
        "swap": {
            "eligible": False,
            "blockers": ["server_duration_probe_required"],
        },
        "ugc": {"eligible": True, "blockers": []},
        "rebuild": {"eligible": True, "blockers": []},
    }


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            "const value=response(); value.assets[0].object_name='private/x.mp4'; return value;",
            "object_keys_mismatch",
        ),
        (
            "const value=response(); value.assets[0].exact_youtube_attached=false; return value;",
            "source_attachment_required",
        ),
        (
            "const value=response(); value.assets[0].duration_seconds=8.1234; return value;",
            "duration_invalid",
        ),
        (
            "const value=response(); value.contract.hashes_returned=true; return value;",
            "unsafe_contract",
        ),
        (
            "const value=response(); value.assets[1].product_identity.product_id=ids.source; return value;",
            "product_identity_invalid",
        ),
        (
            "const value=response(); value.project_id=ids.source; return value;",
            "project_mismatch",
        ),
    ],
)
def test_unsafe_or_mismatched_pages_fail_closed(mutation: str, code: str) -> None:
    result = _evaluate(
        f"""
        (()=>{{
          const raw=(()=>{{{mutation}}})();
          return subject.normalizeGenerationStrategyAssetCandidates(
            raw,{{projectId:ids.project}});
        }})()
        """
    )
    assert result["ok"] is False
    assert result["page"] is None
    assert result["error"]["code"] == code


def test_pages_merge_by_identity_without_reordering_server_keyset_order() -> None:
    result = _evaluate(
        """
        (()=>{
          const first=subject.normalizeGenerationStrategyAssetCandidates(
            response([source()]),{projectId:ids.project}).page;
          const second=subject.normalizeGenerationStrategyAssetCandidates(
            response([product()]),{projectId:ids.project}).page;
          const merged=subject.mergeGenerationStrategyAssetPages(first,second);
          return {ids:merged.assets.map((asset)=>asset.id),frozen:Object.isFrozen(merged.assets)};
        })()
        """
    )
    assert result == {
        "ids": [
            "22222222-2222-4222-8222-222222222222",
            "33333333-3333-4333-8333-333333333333",
        ],
        "frozen": True,
    }
