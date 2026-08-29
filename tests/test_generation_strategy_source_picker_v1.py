from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
SUBJECT = ROOT / "web/app/generation-strategy-source-picker.js"


def _node() -> str:
    value = shutil.which("node")
    if value is None:
        pytest.skip("Node.js is required for source-picker contracts")
    return value


def _run(script: str) -> object:
    with tempfile.TemporaryDirectory() as directory:
        module = Path(directory) / "case.mjs"
        module.write_text(
            f"""
import {{
  GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS as A,
  createGenerationStrategySourcePicker,
  reduceGenerationStrategySourcePicker,
  generationStrategySourcePickerProjection,
  generationStrategySourcePickerSelection,
}} from {json.dumps(SUBJECT.as_uri())};

const uuid = (n) => `${{n.toString(16).padStart(8, '0')}}-1111-4111-8111-${{n.toString(16).padStart(12, '0')}}`;
const strategies = ['viral_avatar_ugc', 'viral_product_swap', 'viral_rebuild'];
const candidate = (n, strategy='viral_product_swap', probe=false) => ({{
  id: uuid(n), kind:'source_video', mime_type:'video/mp4',
  duration_seconds: probe ? null : 8, status:'ready', rights_confirmed:true,
  product_id:null, product_identity:null, filename:`source-${{n}}.mp4`,
  exact_youtube_attached:true, eligible_roles:['source_video'],
  eligible_strategy_roles:[{{strategy_id:strategy,role:'source_video'}}],
  eligible:!probe,
  blocking_codes:probe ? ['server_duration_probe_required'] : [],
  blocking_codes_by_strategy:Object.fromEntries(strategies.map((id) => [
    id, id === strategy ? (probe ? ['server_duration_probe_required'] : []) : ['strategy_role_not_eligible']
  ])),
  created_at:'2026-08-14T10:00:00Z',
  _cursor:{{at:'2026-08-14T10:00:00Z',id:uuid(n)}}, project_id:uuid(900),
}});
const candidates = Array.from({{length:12}}, (_, index) => candidate(index + 1));
const value = (() => {{ {script} }})();
process.stdout.write(JSON.stringify(value));
""",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [_node(), str(module)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout)


def test_rebuild_exact_ten_order_and_limit_are_deterministic() -> None:
    result = _run(
        """
let state=createGenerationStrategySourcePicker('viral_rebuild',candidates.map((item, index) => candidate(index + 1, 'viral_rebuild')),{requiredCount:10});
for(let i=0;i<10;i+=1) state=reduceGenerationStrategySourcePicker(state,{type:A.toggle,source_media_id:uuid(i+1)});
const ten=generationStrategySourcePickerProjection(state);
state=reduceGenerationStrategySourcePicker(state,{type:A.toggle,source_media_id:uuid(11)});
return {ten,after:generationStrategySourcePickerProjection(state),selection:generationStrategySourcePickerSelection(state)};
"""
    )
    assert result["ten"]["selected_count"] == 10
    assert result["ten"]["exactly_ten_selected"] is True
    assert result["ten"]["all_selected_ready"] is True
    assert [row["position"] for row in result["ten"]["selected"]] == list(
        range(1, 11)
    )
    assert result["selection"] == [
        f"{index:08x}-1111-4111-8111-{index:012x}" for index in range(1, 11)
    ]
    assert result["after"]["selected_count"] == 10
    assert result["after"]["error"] == "source_limit_reached"


def test_product_swap_requires_exactly_one_source() -> None:
    result = _run(
        """
const swapCandidates=[candidate(1,'viral_product_swap'),candidate(2,'viral_product_swap')];
let state=createGenerationStrategySourcePicker('viral_product_swap',swapCandidates);
state=reduceGenerationStrategySourcePicker(state,{type:A.toggle,source_media_id:uuid(1)});
const one=generationStrategySourcePickerProjection(state);
state=reduceGenerationStrategySourcePicker(state,{type:A.toggle,source_media_id:uuid(2)});
return {one,after:generationStrategySourcePickerProjection(state),selection:generationStrategySourcePickerSelection(state)};
"""
    )
    assert result["one"]["required_count"] == 1
    assert result["one"]["exact_required_selected"] is True
    assert result["one"]["all_selected_ready"] is True
    assert result["selection"] == ["00000001-1111-4111-8111-000000000001"]
    assert result["after"]["selected_count"] == 1
    assert result["after"]["error"] == "source_limit_reached"


def test_product_swap_accepts_direct_mp4_and_rejects_unattached_video() -> None:
    result = _run(
        """
const direct={
  ...candidate(1,'viral_product_swap'),
  exact_youtube_attached:false,
  direct_mp4_attached:true,
};
const unattached={
  ...candidate(2,'viral_product_swap'),
  exact_youtube_attached:false,
  direct_mp4_attached:false,
};
let state=createGenerationStrategySourcePicker('viral_product_swap',[direct,unattached]);
state=reduceGenerationStrategySourcePicker(state,{type:A.toggle,source_media_id:uuid(1)});
return {
  projection:generationStrategySourcePickerProjection(state),
  candidateIds:state.candidates.map((item)=>item.id),
  selection:generationStrategySourcePickerSelection(state),
};
"""
    )
    assert result["candidateIds"] == ["00000001-1111-4111-8111-000000000001"]
    assert result["projection"]["exact_required_selected"] is True
    assert result["projection"]["all_selected_ready"] is True
    assert result["selection"] == ["00000001-1111-4111-8111-000000000001"]


def test_probe_required_is_selectable_but_cannot_authorize_queue() -> None:
    result = _run(
        """
const list=[candidate(1,'viral_product_swap',true)];
let state=createGenerationStrategySourcePicker('viral_product_swap',list);
state=reduceGenerationStrategySourcePicker(state,{type:A.toggle,source_media_id:uuid(1)});
return {projection:generationStrategySourcePickerProjection(state),selection:generationStrategySourcePickerSelection(state)};
"""
    )
    assert result["selection"] is None
    assert result["projection"]["exact_required_selected"] is True
    assert result["projection"]["all_selected_ready"] is False
    assert result["projection"]["probe_required_source_ids"] == [
        "00000001-1111-4111-8111-000000000001"
    ]


def test_candidate_refresh_preserves_order_and_drops_only_missing_source() -> None:
    result = _run(
        """
const rebuildCandidates=candidates.map((item,index)=>candidate(index+1,'viral_rebuild'));
let state=createGenerationStrategySourcePicker('viral_rebuild',rebuildCandidates,{requiredCount:10});
for(let i=0;i<10;i+=1) state=reduceGenerationStrategySourcePicker(state,{type:A.toggle,source_media_id:uuid(i+1)});
const before=state.revision;
state=reduceGenerationStrategySourcePicker(state,{type:A.replaceCandidates,strategy_id:'viral_rebuild',candidates:rebuildCandidates.filter((_,index)=>index!==4)});
return {before,projection:generationStrategySourcePickerProjection(state)};
"""
    )
    assert result["projection"]["revision"] == result["before"] + 1
    assert result["projection"]["selected_count"] == 9
    assert [row["source_media_id"] for row in result["projection"]["selected"]] == [
        f"{index:08x}-1111-4111-8111-{index:012x}"
        for index in [1, 2, 3, 4, 6, 7, 8, 9, 10]
    ]


def test_strategy_change_clears_selection_without_inference() -> None:
    result = _run(
        """
let state=createGenerationStrategySourcePicker('viral_product_swap',candidates);
state=reduceGenerationStrategySourcePicker(state,{type:A.toggle,source_media_id:uuid(1)});
state=reduceGenerationStrategySourcePicker(state,{type:A.replaceCandidates,strategy_id:'viral_rebuild',candidates:[candidate(20,'viral_rebuild')]});
return generationStrategySourcePickerProjection(state);
"""
    )
    assert result["strategy_id"] == "viral_rebuild"
    assert result["selected_count"] == 0


def test_projection_contains_no_launch_or_storage_authority() -> None:
    source = SUBJECT.read_text(encoding="utf-8")
    for forbidden in (
        "signed_url",
        "object_name",
        "bucket_id",
        "spend_confirmation",
        "receipt_hash",
        "binding_hash",
        "provider_task",
        "fetch(",
        "localStorage",
        "sessionStorage",
        "Date.now",
        "Math.random",
        "crypto.randomUUID",
    ):
        assert forbidden not in source

    result = _run(
        """
let state=createGenerationStrategySourcePicker('viral_product_swap',candidates);
state=reduceGenerationStrategySourcePicker(state,{type:A.toggle,source_media_id:uuid(1)});
return generationStrategySourcePickerProjection(state);
"""
    )
    serialized = json.dumps(result, sort_keys=True)
    for forbidden in ("url", "hash", "provider", "price", "prompt", "attestation"):
        assert forbidden not in serialized.lower()


def test_module_is_syntax_valid() -> None:
    completed = subprocess.run(
        [_node(), "--check", str(SUBJECT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_rebuild_defaults_to_single_and_batch_mode_is_explicit_state() -> None:
    """M1 (29.08.2026): требование — состояние пикера. Дефолт «Создания» —
    один референс-хит (боевой режим 26-29.08); пакет из десяти включается
    только явным SET_REQUIRED_COUNT и запрещён «Копии»/«Дуэту». Сжатие
    пакета до одиночного режима оставляет первый выбранный ролик."""
    result = _run(
        """
let state=createGenerationStrategySourcePicker('viral_rebuild',candidates.map((item, index) => candidate(index + 1, 'viral_rebuild')));
const single=generationStrategySourcePickerProjection(state);
state=reduceGenerationStrategySourcePicker(state,{type:A.setRequiredCount,required_count:10});
state=reduceGenerationStrategySourcePicker(state,{type:A.toggle,source_media_id:uuid(1)});
state=reduceGenerationStrategySourcePicker(state,{type:A.toggle,source_media_id:uuid(2)});
state=reduceGenerationStrategySourcePicker(state,{type:A.toggle,source_media_id:uuid(3)});
const batch=generationStrategySourcePickerProjection(state);
state=reduceGenerationStrategySourcePicker(state,{type:A.replaceCandidates,strategy_id:'viral_rebuild',candidates:candidates.map((item, index) => candidate(index + 1, 'viral_rebuild'))});
const afterRefresh=generationStrategySourcePickerProjection(state);
state=reduceGenerationStrategySourcePicker(state,{type:A.setRequiredCount,required_count:1});
const shrunk=generationStrategySourcePickerProjection(state);
const invalidMode=reduceGenerationStrategySourcePicker(state,{type:A.setRequiredCount,required_count:7});
const swap=createGenerationStrategySourcePicker('viral_product_swap',[candidate(1,'viral_product_swap')],{requiredCount:10});
return {single,batch,afterRefresh,shrunk,invalidError:generationStrategySourcePickerProjection(invalidMode).error,swapIsNull:swap===null};
"""
    )
    assert result["single"]["required_count"] == 1
    assert result["batch"]["required_count"] == 10
    assert result["batch"]["selected_count"] == 3
    assert result["afterRefresh"]["required_count"] == 10
    assert result["afterRefresh"]["selected_count"] == 3
    assert result["shrunk"]["required_count"] == 1
    assert result["shrunk"]["selected_count"] == 1
    assert result["shrunk"]["exact_required_selected"] is True
    assert result["shrunk"]["selected"][0]["source_media_id"].startswith("00000001")
    assert result["invalidError"] == "required_count_unsupported"
    assert result["swapIsNull"] is True
