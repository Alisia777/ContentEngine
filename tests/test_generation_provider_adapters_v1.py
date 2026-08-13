from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
CATALOG_MODULE = ROOT / "supabase/functions/_shared/generation-model-catalog.js"
ADAPTER_MODULE = ROOT / "supabase/functions/_shared/generation-provider-adapters.js"
CATALOG_SOURCE = CATALOG_MODULE.read_text(encoding="utf-8")
ADAPTER_SOURCE = ADAPTER_MODULE.read_text(encoding="utf-8")

PRELUDE = r"""
const flags = {
  [catalog.GENERATION_MODEL_FEATURE_FLAGS.runwayPremium]: true,
  [catalog.GENERATION_MODEL_FEATURE_FLAGS.googleVeoLite]: true,
};
const get = (provider, model) => catalog.generationModelCatalogEntry(provider, model);
const selection = (provider, model, value) => {
  const result = catalog.validateGenerationModelSelection(
    get(provider, model), value, {featureFlags: flags},
  );
  if (!result.ok) throw new Error(`test_selection:${result.code}`);
  return result;
};
const build = (provider, model, selected, input) => subject.buildGenerationProviderRequest(
  get(provider, model), selected, input,
);
const attempt = (callback) => {
  try {
    return {ok: true, value: callback()};
  } catch (error) {
    return {ok: false, code: error?.code || "", message: error?.message || ""};
  }
};
const image = {mimeType: "image/png", data: "aGVsbG8="};
"""


def _evaluate(expression: str, *, catalog_source: str = CATALOG_SOURCE) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for provider adapter contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text(
            '{"type":"module"}', encoding="utf-8"
        )
        (directory / "generation-model-catalog.js").write_text(
            catalog_source, encoding="utf-8"
        )
        (directory / "generation-provider-adapters.js").write_text(
            ADAPTER_SOURCE, encoding="utf-8"
        )
        (directory / "contract.js").write_text(
            "import * as catalog from './generation-model-catalog.js';\n"
            "import * as subject from './generation-provider-adapters.js';\n"
            f"{PRELUDE}\n"
            f"const result = {expression};\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.js"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_adapter_is_pure_inert_and_exports_no_dispatch_capability() -> None:
    for forbidden in (
        "Deno.env",
        "process.env",
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "document.",
        "window.",
        "WebSocket",
        "setTimeout(",
    ):
        assert forbidden not in ADAPTER_SOURCE

    result = _evaluate(
        """
        (() => {
          const entry = get("runway", "gen4_turbo");
          const selected = selection("runway", "gen4_turbo", {
            inputMode: "image", durationSeconds: 5, ratio: "9:16",
            resolution: "720p", firstFrame: true,
          });
          const request = build("runway", "gen4_turbo", selected, {
            promptText: "Product turntable", firstFrameUrl: "https://media.example/a.png?sig=opaque",
          });
          return {
            exports: Object.keys(subject).sort(),
            keys: Object.keys(request),
            bodyKeys: Object.keys(request.body),
            frozen: Object.isFrozen(request) && Object.isFrozen(request.body),
            serialized: JSON.stringify(request),
          };
        })()
        """
    )
    assert result["exports"] == [
        "GENERATION_PROVIDER_POLL_KINDS",
        "GenerationProviderAdapterError",
        "buildGenerationProviderRequest",
    ]
    assert result["keys"] == [
        "provider",
        "endpointPath",
        "method",
        "body",
        "pollKind",
    ]
    assert result["bodyKeys"] == [
        "model",
        "promptText",
        "promptImage",
        "ratio",
        "duration",
    ]
    assert result["frozen"] is True
    serialized = result["serialized"].lower()
    assert "apikey" not in serialized
    assert "authorization" not in serialized
    assert "bearer" not in serialized


def test_every_catalog_model_and_supported_mode_builds_the_exact_endpoint() -> None:
    result = _evaluate(
        r"""
        (() => {
          const urls = {
            firstFrameUrl: "https://media.example/first.png?sig=one",
            lastFrameUrl: "https://media.example/last.png?sig=two",
            inputVideoUrl: "https://media.example/input.mp4?sig=three",
          };
          const records = [];
          const add = (provider, model, value, input) => {
            const selected = selection(provider, model, value);
            const request = build(provider, model, selected, input);
            records.push({
              key: `${provider}:${model}:${value.inputMode}`,
              endpoint: request.endpointPath,
              method: request.method,
              pollKind: request.pollKind,
              keys: Object.keys(request),
            });
          };

          add("runway", "seedream5_lite", {inputMode:"text",durationSeconds:0,ratio:"1:1",resolution:"2K"}, {promptText:"Studio product photo"});
          add("runway", "seedream5_lite", {inputMode:"image",durationSeconds:0,ratio:"1:1",resolution:"2K",referenceImageCount:2}, {promptText:"Studio product photo",referenceImageUrls:["https://media.example/r1.png","https://media.example/r2.png"]});
          add("runway", "gen4_turbo", {inputMode:"image",durationSeconds:5,ratio:"9:16",resolution:"720p",firstFrame:true}, {promptText:"Slow orbit",firstFrameUrl:urls.firstFrameUrl});

          for (const model of ["seedance2_fast", "seedance2_mini", "seedance2"]) {
            add("runway", model, {inputMode:"text",durationSeconds:5,ratio:"16:9",resolution:"720p",audio:true,spokenDialogue:true,referenceImageCount:2,referenceVideo:true}, {promptText:"A presenter speaks",referenceImageUrls:["https://media.example/r1.png","https://media.example/r2.png"],referenceVideoUrls:["https://media.example/rv1.mp4"]});
            add("runway", model, {inputMode:"image",durationSeconds:8,ratio:"16:9",resolution:"720p",audio:true,firstFrame:true,lastFrame:true}, {promptText:"Transition",firstFrameUrl:urls.firstFrameUrl,lastFrameUrl:urls.lastFrameUrl});
            add("runway", model, {inputMode:"video",durationSeconds:6,ratio:"9:16",resolution:"720p",audio:true,referenceImageCount:1,referenceVideo:true}, {promptText:"Restyle clip",inputVideoUrl:urls.inputVideoUrl,referenceImageUrls:["https://media.example/r1.png"],referenceVideoUrls:["https://media.example/rv1.mp4","https://media.example/rv2.mp4"]});
          }

          add("runway", "gen4.5", {inputMode:"text",durationSeconds:6,ratio:"16:9",resolution:"720p"}, {promptText:"Cinematic dolly"});
          add("runway", "gen4.5", {inputMode:"image",durationSeconds:6,ratio:"4:3",resolution:"720p",firstFrame:true}, {promptText:"Cinematic dolly",firstFrameUrl:urls.firstFrameUrl});

          for (const model of ["veo3.1_fast", "veo3.1"]) {
            add("runway", model, {inputMode:"text",durationSeconds:6,ratio:"16:9",resolution:"720p",audio:false}, {promptText:"Silent landscape"});
            add("runway", model, {inputMode:"image",durationSeconds:8,ratio:"9:16",resolution:"1080p",audio:true,firstFrame:true,lastFrame:true}, {promptText:"Dialogue scene",firstFrameUrl:urls.firstFrameUrl,lastFrameUrl:urls.lastFrameUrl});
          }

          add("runway", "gemini_omni_flash", {inputMode:"text",durationSeconds:5,ratio:"16:9",resolution:"720p",audio:true}, {promptText:"Fast concept"});
          add("runway", "gemini_omni_flash", {inputMode:"image",durationSeconds:5,ratio:"9:16",resolution:"720p",audio:true,firstFrame:true}, {promptText:"Animate product",firstFrameUrl:urls.firstFrameUrl});
          add("runway", "gemini_omni_flash", {inputMode:"video",durationSeconds:7,ratio:"9:16",resolution:"720p",audio:true,referenceVideo:true,referenceImageCount:2}, {promptText:"Edit product clip",inputVideoUrl:urls.inputVideoUrl,inputVideoDurationSeconds:7,inputVideoRatio:"9:16",referenceImageUrls:["https://media.example/r1.png","https://media.example/r2.png"]});

          add("google", "veo-3.1-lite-generate-preview", {inputMode:"text",durationSeconds:4,ratio:"16:9",resolution:"720p",audio:true}, {promptText:"Wide product reveal"});
          add("google", "veo-3.1-lite-generate-preview", {inputMode:"image",durationSeconds:8,ratio:"9:16",resolution:"1080p",audio:true,firstFrame:true,lastFrame:true}, {promptText:"Vertical transition",imageInlineData:image,lastFrameInlineData:{mimeType:"image/jpeg",data:"aGVsbG8="}});
          return records;
        })()
        """
    )
    assert len(result) == 23
    assert len({row["key"] for row in result}) == 23
    expected_by_mode = {
        "seedream5_lite:text": "/v1/text_to_image",
        "seedream5_lite:image": "/v1/text_to_image",
        "gen4_turbo:image": "/v1/image_to_video",
        "gen4.5:text": "/v1/text_to_video",
        "gen4.5:image": "/v1/image_to_video",
    }
    for row in result:
        provider, model, mode = row["key"].split(":")
        if provider == "google":
            assert row["endpoint"] == (
                "/v1beta/models/veo-3.1-lite-generate-preview:predictLongRunning"
            )
            assert row["pollKind"] == "google_long_running_operation"
        elif f"{model}:{mode}" in expected_by_mode:
            assert row["endpoint"] == expected_by_mode[f"{model}:{mode}"]
            assert row["pollKind"] == "runway_task"
        else:
            assert row["endpoint"] == {
                "text": "/v1/text_to_video",
                "image": "/v1/image_to_video",
                "video": "/v1/video_to_video",
            }[mode]
            assert row["pollKind"] == "runway_task"
        assert row["method"] == "POST"
        assert row["keys"] == [
            "provider", "endpointPath", "method", "body", "pollKind"
        ]


def test_runway_body_shapes_preserve_urls_and_catalog_provider_dimensions() -> None:
    result = _evaluate(
        r"""
        (() => {
          const signed = "https://media.example/product.png?X-Signature=A%2BB%3D&part=1";
          const seedreamSelection = selection("runway", "seedream5_lite", {
            inputMode:"image",durationSeconds:0,ratio:"16:9",resolution:"2K",referenceImageCount:1,
          });
          const seedanceText = selection("runway", "seedance2_fast", {
            inputMode:"text",durationSeconds:5,ratio:"16:9",resolution:"720p",audio:true,
            referenceImageCount:1,referenceVideo:true,
          });
          const seedanceFrames = selection("runway", "seedance2_fast", {
            inputMode:"image",durationSeconds:8,ratio:"9:16",resolution:"720p",audio:true,
            firstFrame:true,lastFrame:true,
          });
          const seedanceVideo = selection("runway", "seedance2_fast", {
            inputMode:"video",durationSeconds:6,ratio:"1:1",resolution:"480p",audio:false,
          });
          const runwayVeo = selection("runway", "veo3.1_fast", {
            inputMode:"image",durationSeconds:8,ratio:"9:16",resolution:"1080p",audio:true,
            firstFrame:true,lastFrame:true,
          });
          const omniVideo = selection("runway", "gemini_omni_flash", {
            inputMode:"video",durationSeconds:7,ratio:"9:16",resolution:"720p",audio:true,
            referenceVideo:true,referenceImageCount:1,
          });
          return {
            seedream: build("runway", "seedream5_lite", seedreamSelection, {
              promptText:"Exact photo",referenceImageUrls:[signed],
            }).body,
            seedanceText: build("runway", "seedance2_fast", seedanceText, {
              promptText:"Exact text",referenceImageUrls:[signed],
              referenceVideoUrls:["https://media.example/ref.mp4?sig=opaque"],
            }).body,
            seedanceFrames: build("runway", "seedance2_fast", seedanceFrames, {
              promptText:"Exact frames",firstFrameUrl:signed,lastFrameUrl:"https://media.example/last.png",
            }).body,
            seedanceVideo: build("runway", "seedance2_fast", seedanceVideo, {
              promptText:"Exact video",inputVideoUrl:"https://media.example/input.mp4?sig=opaque",
            }).body,
            runwayVeo: build("runway", "veo3.1_fast", runwayVeo, {
              promptText:"Veo frames",firstFrameUrl:signed,lastFrameUrl:"https://media.example/last.png",
            }).body,
            omniVideo: build("runway", "gemini_omni_flash", omniVideo, {
              promptText:"Omni edit",inputVideoUrl:"https://media.example/input.mp4?sig=opaque",
              inputVideoDurationSeconds:7,inputVideoRatio:"9:16",referenceImageUrls:[signed],
            }).body,
          };
        })()
        """
    )
    assert result["seedream"] == {
        "model": "seedream5_lite",
        "promptText": "Exact photo",
        "ratio": "2848:1600",
        "outputFormat": "png",
        "outputCount": 1,
        "referenceImages": [
            {
                "uri": (
                    "https://media.example/product.png?"
                    "X-Signature=A%2BB%3D&part=1"
                ),
                "tag": "ProductReference",
            }
        ],
    }
    assert result["seedanceText"]["ratio"] == "1280:720"
    assert result["seedanceText"]["references"] == [
        {
            "uri": (
                "https://media.example/product.png?"
                "X-Signature=A%2BB%3D&part=1"
            )
        }
    ]
    assert result["seedanceText"]["referenceVideos"] == [
        {"type": "video", "uri": "https://media.example/ref.mp4?sig=opaque"}
    ]
    assert result["seedanceFrames"]["promptImage"] == [
        {
            "uri": (
                "https://media.example/product.png?"
                "X-Signature=A%2BB%3D&part=1"
            ),
            "position": "first",
        },
        {"uri": "https://media.example/last.png", "position": "last"},
    ]
    assert "references" not in result["seedanceFrames"]
    assert result["seedanceVideo"]["promptVideo"] == (
        "https://media.example/input.mp4?sig=opaque"
    )
    assert result["seedanceVideo"]["ratio"] == "640:640"
    assert result["runwayVeo"]["ratio"] == "1080:1920"
    assert result["runwayVeo"]["promptImage"][1]["position"] == "last"
    assert result["omniVideo"] == {
        "model": "gemini_omni_flash",
        "promptText": "Omni edit",
        "videoUri": "https://media.example/input.mp4?sig=opaque",
        "references": [
            {
                "uri": (
                    "https://media.example/product.png?"
                    "X-Signature=A%2BB%3D&part=1"
                )
            }
        ],
    }


def test_google_veo_lite_uses_exact_rest_shape_and_inline_frames_only() -> None:
    result = _evaluate(
        r"""
        (() => {
          const text = selection("google", "veo-3.1-lite-generate-preview", {
            inputMode:"text",durationSeconds:4,ratio:"16:9",resolution:"720p",audio:true,
          });
          const frames = selection("google", "veo-3.1-lite-generate-preview", {
            inputMode:"image",durationSeconds:8,ratio:"9:16",resolution:"1080p",audio:true,
            firstFrame:true,lastFrame:true,spokenDialogue:true,
          });
          return {
            text: build("google", "veo-3.1-lite-generate-preview", text, {promptText:"Product reveal"}),
            frames: build("google", "veo-3.1-lite-generate-preview", frames, {
              promptText:"Speaker says hello",imageInlineData:image,
              lastFrameInlineData:{mimeType:"image/webp",data:"d29ybGQ="},
            }),
          };
        })()
        """
    )
    assert result["text"] == {
        "provider": "google",
        "endpointPath": (
            "/v1beta/models/veo-3.1-lite-generate-preview:predictLongRunning"
        ),
        "method": "POST",
        "body": {
            "instances": [{"prompt": "Product reveal"}],
            "parameters": {
                "numberOfVideos": 1,
                "aspectRatio": "16:9",
                "resolution": "720p",
                "durationSeconds": 4,
            },
        },
        "pollKind": "google_long_running_operation",
    }
    assert result["frames"]["body"] == {
        "instances": [
            {
                "prompt": "Speaker says hello",
                "image": {
                    "inlineData": {
                        "mimeType": "image/png",
                        "data": "aGVsbG8=",
                    }
                },
                "lastFrame": {
                    "inlineData": {
                        "mimeType": "image/webp",
                        "data": "d29ybGQ=",
                    }
                },
            }
        ],
        "parameters": {
            "numberOfVideos": 1,
            "aspectRatio": "9:16",
            "resolution": "1080p",
            "durationSeconds": 8,
        },
    }
    serialized = json.dumps(result).lower()
    assert "apikey" not in serialized
    assert "authorization" not in serialized
    assert "imageurl" not in serialized
    assert "fileuri" not in serialized


def test_strict_allowlist_rejects_secrets_urls_and_incompatible_fields_without_leak() -> None:
    result = _evaluate(
        r"""
        (() => {
          const gen4 = selection("runway", "gen4_turbo", {
            inputMode:"image",durationSeconds:5,ratio:"9:16",resolution:"720p",firstFrame:true,
          });
          const googleImage = selection("google", "veo-3.1-lite-generate-preview", {
            inputMode:"image",durationSeconds:8,ratio:"9:16",resolution:"720p",audio:true,firstFrame:true,
          });
          const secretValue = "DO_NOT_LEAK_SUPER_SECRET";
          const cases = {
            apiKey: attempt(() => build("runway", "gen4_turbo", gen4, {promptText:"x",firstFrameUrl:"https://media.example/a.png",apiKey:secretValue})),
            authorization: attempt(() => build("runway", "gen4_turbo", gen4, {promptText:"x",firstFrameUrl:"https://media.example/a.png",authorization:`Bearer ${secretValue}`})),
            http: attempt(() => build("runway", "gen4_turbo", gen4, {promptText:"x",firstFrameUrl:"http://media.example/a.png"})),
            credentials: attempt(() => build("runway", "gen4_turbo", gen4, {promptText:"x",firstFrameUrl:"https://user:pass@media.example/a.png"})),
            fragment: attempt(() => build("runway", "gen4_turbo", gen4, {promptText:"x",firstFrameUrl:"https://media.example/a.png#fragment"})),
            googleUrl: attempt(() => build("google", "veo-3.1-lite-generate-preview", googleImage, {promptText:"x",imageUrl:"https://media.example/a.png"})),
            googleFile: attempt(() => build("google", "veo-3.1-lite-generate-preview", googleImage, {promptText:"x",fileUri:"https://media.example/a.png"})),
            inlineExtra: attempt(() => build("google", "veo-3.1-lite-generate-preview", googleImage, {promptText:"x",imageInlineData:{...image,apiKey:secretValue}})),
            inlineMime: attempt(() => build("google", "veo-3.1-lite-generate-preview", googleImage, {promptText:"x",imageInlineData:{mimeType:"image/svg+xml",data:"aGVsbG8="}})),
            inlineDataUri: attempt(() => build("google", "veo-3.1-lite-generate-preview", googleImage, {promptText:"x",imageInlineData:{mimeType:"image/png",data:"data:image/png;base64,aGVsbG8="}})),
          };
          return {cases, leaked: JSON.stringify(cases).includes(secretValue)};
        })()
        """
    )
    assert result["leaked"] is False
    assert result["cases"]["apiKey"]["code"] == "input_field_unknown"
    assert result["cases"]["authorization"]["code"] == "input_field_unknown"
    assert result["cases"]["http"]["code"] == "first_frame_url_invalid"
    assert result["cases"]["credentials"]["code"] == "first_frame_url_invalid"
    assert result["cases"]["fragment"]["code"] == "first_frame_url_invalid"
    assert result["cases"]["googleUrl"]["code"] == "input_field_unknown"
    assert result["cases"]["googleFile"]["code"] == "input_field_unknown"
    assert result["cases"]["inlineExtra"]["code"] == "image_inline_data_invalid"
    assert result["cases"]["inlineMime"]["code"] == "image_inline_data_invalid"
    assert result["cases"]["inlineDataUri"]["code"] == "image_inline_data_invalid"


def test_model_specific_constraints_fail_closed() -> None:
    result = _evaluate(
        r"""
        (() => {
          const seedanceMixed = selection("runway", "seedance2_fast", {
            inputMode:"image",durationSeconds:8,ratio:"16:9",resolution:"720p",audio:true,
            firstFrame:true,referenceImageCount:1,
          });
          const seedanceLastOnly = selection("runway", "seedance2_fast", {
            inputMode:"image",durationSeconds:8,ratio:"16:9",resolution:"720p",audio:true,lastFrame:true,
          });
          const seedanceTextVideo = selection("runway", "seedance2_fast", {
            inputMode:"text",durationSeconds:5,ratio:"16:9",resolution:"720p",audio:true,referenceVideo:true,
          });
          const omniSilent = selection("runway", "gemini_omni_flash", {
            inputMode:"text",durationSeconds:5,ratio:"16:9",resolution:"720p",audio:false,
          });
          const omniVideo = selection("runway", "gemini_omni_flash", {
            inputMode:"video",durationSeconds:7,ratio:"9:16",resolution:"720p",audio:true,referenceVideo:true,
          });
          const googleSilent = selection("google", "veo-3.1-lite-generate-preview", {
            inputMode:"text",durationSeconds:4,ratio:"16:9",resolution:"720p",audio:false,
          });
          const googleLastSix = {...selection("google", "veo-3.1-lite-generate-preview", {
            inputMode:"image",durationSeconds:8,ratio:"16:9",resolution:"720p",audio:true,
            firstFrame:true,lastFrame:true,
          }), durationSeconds:6};
          return {
            mixed: attempt(() => build("runway", "seedance2_fast", seedanceMixed, {promptText:"x",firstFrameUrl:"https://media.example/first.png",referenceImageUrls:["https://media.example/ref.png"]})),
            lastOnly: attempt(() => build("runway", "seedance2_fast", seedanceLastOnly, {promptText:"x",lastFrameUrl:"https://media.example/last.png"})),
            tooManyVideos: attempt(() => build("runway", "seedance2_fast", seedanceTextVideo, {promptText:"x",referenceVideoUrls:["https://media.example/1.mp4","https://media.example/2.mp4","https://media.example/3.mp4","https://media.example/4.mp4"]})),
            omniSilent: attempt(() => build("runway", "gemini_omni_flash", omniSilent, {promptText:"x"})),
            omniDuration: attempt(() => build("runway", "gemini_omni_flash", omniVideo, {promptText:"x",inputVideoUrl:"https://media.example/in.mp4",inputVideoDurationSeconds:6,inputVideoRatio:"9:16"})),
            omniRatio: attempt(() => build("runway", "gemini_omni_flash", omniVideo, {promptText:"x",inputVideoUrl:"https://media.example/in.mp4",inputVideoDurationSeconds:7,inputVideoRatio:"16:9"})),
            googleSilent: attempt(() => build("google", "veo-3.1-lite-generate-preview", googleSilent, {promptText:"x"})),
            googleLastSix: attempt(() => build("google", "veo-3.1-lite-generate-preview", googleLastSix, {promptText:"x",imageInlineData:image,lastFrameInlineData:image})),
          };
        })()
        """
    )
    assert result["mixed"]["code"] == "seedance_keyframes_references_mixed"
    assert result["lastOnly"]["code"] == "last_frame_requires_first_frame"
    assert result["tooManyVideos"]["code"] == "reference_video_urls_invalid"
    assert result["omniSilent"]["code"] == "audio_is_inherent"
    assert result["omniDuration"]["code"] == "omni_input_video_metadata_mismatch"
    assert result["omniRatio"]["code"] == "omni_input_video_metadata_mismatch"
    assert result["googleSilent"]["code"] == "audio_is_inherent"
    assert result["googleLastSix"]["code"] == "google_last_frame_duration_invalid"


def test_catalog_prompt_limits_and_exact_reference_counts_are_enforced() -> None:
    result = _evaluate(
        r"""
        (() => {
          const selections = {
            seedream: selection("runway", "seedream5_lite", {inputMode:"text",durationSeconds:0,ratio:"1:1",resolution:"2K"}),
            gen4: selection("runway", "gen4_turbo", {inputMode:"image",durationSeconds:5,ratio:"9:16",resolution:"720p",firstFrame:true}),
            seedance: selection("runway", "seedance2_fast", {inputMode:"text",durationSeconds:5,ratio:"16:9",resolution:"720p",audio:true}),
            omni: selection("runway", "gemini_omni_flash", {inputMode:"text",durationSeconds:5,ratio:"16:9",resolution:"720p",audio:true}),
            google: selection("google", "veo-3.1-lite-generate-preview", {inputMode:"text",durationSeconds:4,ratio:"16:9",resolution:"720p",audio:true}),
            refs: selection("runway", "seedream5_lite", {inputMode:"image",durationSeconds:0,ratio:"1:1",resolution:"2K",referenceImageCount:2}),
          };
          return {
            seedream: attempt(() => build("runway", "seedream5_lite", selections.seedream, {promptText:"x".repeat(4001)})),
            gen4: attempt(() => build("runway", "gen4_turbo", selections.gen4, {promptText:"x".repeat(1001),firstFrameUrl:"https://media.example/a.png"})),
            gen4Utf16: attempt(() => build("runway", "gen4_turbo", selections.gen4, {promptText:"😀".repeat(501),firstFrameUrl:"https://media.example/a.png"})),
            seedance: attempt(() => build("runway", "seedance2_fast", selections.seedance, {promptText:"x".repeat(3501)})),
            omni: attempt(() => build("runway", "gemini_omni_flash", selections.omni, {promptText:"x".repeat(4001)})),
            google: attempt(() => build("google", "veo-3.1-lite-generate-preview", selections.google, {promptText:"x".repeat(1025)})),
            refsMissing: attempt(() => build("runway", "seedream5_lite", selections.refs, {promptText:"x",referenceImageUrls:["https://media.example/a.png"]})),
            refsExtra: attempt(() => build("runway", "seedream5_lite", selections.refs, {promptText:"x",referenceImageUrls:["https://media.example/a.png","https://media.example/b.png","https://media.example/c.png"]})),
          };
        })()
        """
    )
    for key in ("seedream", "gen4", "gen4Utf16", "seedance", "omni", "google"):
        assert result[key]["code"] == "prompt_too_long"
    assert result["refsMissing"]["code"] == "reference_image_urls_invalid"
    assert result["refsExtra"]["code"] == "reference_image_urls_invalid"


def test_exact_selection_binding_and_missing_provider_ratio_fail_closed() -> None:
    result = _evaluate(
        r"""
        (() => {
          const entry = get("runway", "gen4_turbo");
          const selected = selection("runway", "gen4_turbo", {
            inputMode:"image",durationSeconds:5,ratio:"9:16",resolution:"720p",firstFrame:true,
          });
          const input = {promptText:"x",firstFrameUrl:"https://media.example/a.png"};
          return {
            clonedEntry: attempt(() => subject.buildGenerationProviderRequest({...entry}, selected, input)),
            selectionExtra: attempt(() => subject.buildGenerationProviderRequest(entry, {...selected, estimatedCostMinor:25}, input)),
            selectionModel: attempt(() => subject.buildGenerationProviderRequest(entry, {...selected, model:"gen4.5"}, input)),
          };
        })()
        """
    )
    assert result["clonedEntry"]["code"] == "catalog_entry_not_canonical"
    assert result["selectionExtra"]["code"] == "selection_not_exact"
    assert result["selectionModel"]["code"] == "selection_binding_invalid"

    catalog_without_gen4_ratios = CATALOG_SOURCE.replace(
        "providerRatios: GEN4_PROVIDER_RATIOS,",
        "providerRatios: {},",
        1,
    ).replace("\nassertCatalog();", "\n// Catalog bootstrap assertion omitted in this fault-injection fixture.")
    assert catalog_without_gen4_ratios != CATALOG_SOURCE
    ratio_result = _evaluate(
        r"""
        (() => {
          const selected = selection("runway", "gen4_turbo", {
            inputMode:"image",durationSeconds:5,ratio:"9:16",resolution:"720p",firstFrame:true,
          });
          return attempt(() => build("runway", "gen4_turbo", selected, {
            promptText:"x",firstFrameUrl:"https://media.example/a.png",
          }));
        })()
        """,
        catalog_source=catalog_without_gen4_ratios,
    )
    assert ratio_result["code"] == "provider_ratio_missing"
