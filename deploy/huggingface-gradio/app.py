"""
Hugging Face Space entry point (Gradio SDK; works on ZeroGPU hardware).

Free Spaces must be Gradio apps, and ZeroGPU hardware additionally
requires a @spaces.GPU function to be registered when Gradio launches.
busiRAG does not need a GPU (its small models run on CPU), so this
file launches a minimal Gradio app and serves busiRAG inside the same
server:

    /           Gradio page that redirects to /busirag/
    /busirag/   busiRAG frontend (prebuilt, in ./dist) and API

Build the frontend for the /busirag/ prefix (see DEPLOYMENT.md):

    VITE_API_BASE_URL=/busirag npm run build -- --base=/busirag/

Space secrets: DATABASE_URL, REDIS_URL, GEMINI_API_KEY, JWT_SECRET_KEY.
Migrations are run from your machine (alembic upgrade head) beforehand.
"""

import inspect
import os
from pathlib import Path

# On ZeroGPU the `spaces` package must be imported before torch.
try:
    import spaces
except ImportError:  # running outside Hugging Face
    spaces = None

HERE = Path(__file__).resolve().parent
PREFIX = "/busirag"

# Read when busirag.api.main is imported, so set them first.
os.environ.setdefault("FRONTEND_DIST", str(HERE / "dist"))
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("RETRIEVAL_MODE", "hybrid")
os.environ.setdefault("CACHE_TTL", "2592000")
# ZeroGPU reports a GPU that is only usable inside @spaces.GPU calls.
os.environ.setdefault("MODEL_DEVICE", "cpu")
# Behind the Spaces proxy: let uvicorn use X-Forwarded-For so the
# per-client rate limit sees real client IPs.
os.environ.setdefault("FORWARDED_ALLOW_IPS", "*")

import gradio as gr  # noqa: E402
from starlette.routing import Mount  # noqa: E402

from busirag.api.main import app as busirag_app  # noqa: E402
from busirag.api.main import initialize_app_state  # noqa: E402


def _gpu_placeholder() -> str:
    """Never needs a GPU; registered only because ZeroGPU requires one."""

    return "ok"


if spaces is not None:
    _gpu_placeholder = spaces.GPU(_gpu_placeholder)


# Mounted apps do not run their lifespan, so load models and services now.
initialize_app_state(busirag_app)

# Send visitors straight to the busiRAG UI with a script that runs when
# the Gradio page loads. Gradio 6 takes `js` in launch(); older versions
# take it in the Blocks constructor.
REDIRECT_JS = f"() => {{ window.location.replace('{PREFIX}/'); }}"
JS_IN_LAUNCH = "js" in inspect.signature(gr.Blocks.launch).parameters

with gr.Blocks(
    title="busiRAG",
    **({} if JS_IN_LAUNCH else {"js": REDIRECT_JS}),
) as demo:
    gr.Markdown(
        f"# busiRAG\n\nOpening the demo… If nothing happens, "
        f"[open busiRAG]({PREFIX}/)."
    )

    # Hidden event bound to the GPU function, so ZeroGPU detects it.
    placeholder_button = gr.Button(visible=False)
    placeholder_output = gr.Textbox(visible=False)
    placeholder_button.click(_gpu_placeholder, outputs=placeholder_output)


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),
        # Registered before Gradio's own routes, so /busirag/* is served
        # by busiRAG and everything else by Gradio.
        app_kwargs={"routes": [Mount(PREFIX, app=busirag_app)]},
        **({"js": REDIRECT_JS} if JS_IN_LAUNCH else {}),
    )
