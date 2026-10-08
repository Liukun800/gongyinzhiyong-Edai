# Vendored source and local change

model.py and contract.py originate from li-xiu-qi/XiaokeAILabs, commit
24277dc067e2c1809013068a559c6b273b202d5d,
experiments/test_jev_open_source/text_jev_train/{agentjev/model.py,jev_service/contract.py}.
The upstream credits malevrigns/agent-jev. License: Apache-2.0; LICENSE retained.

Local modification, 2026-09-27: add optional backbone_config to AgentJevModel
so a full published safetensors state dict can load without separately
downloading the Qwen base weights. Candidate encoding and scoring are unchanged.
Local serving uses independent candidate paths, not prefix cache reuse.

This is not TypeSafe Jev official weights and has not been bank-domain trained
or calibrated. The published checkpoint's model card and source hashes are
preserved in models/agentjev-public. Do not assign the GitHub benchmark score
to the downloaded checkpoint: the fixed model card describes a coding-completion
checkpoint, which differs from the generic benchmark narrative.
