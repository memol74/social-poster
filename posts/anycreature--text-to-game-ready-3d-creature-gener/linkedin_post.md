🚨 Game dev reality check:

You need 50 enemy types for your indie game. Hiring a 3D artist costs $5K per creature. Fiverr takes two weeks per model. Asset packs all look the same.

Someone just open sourced anyCreature — a text-to-creature compiler that ships game-ready GLBs in one session.

You type "menacing mountain giant," answer at most two questions, and the engine compiles a skinned, rigged, vertex-colored character with animations. No mesh files. No downloaded art packs. No photogrammetry. The example wolf is 2,211 vertices written from plain JSON.

✅ Zero runtime dependencies — node cli.js spec.json out.glb is the whole interface
✅ Automated quality gates with context-free silhouette readers so nothing ships broken
✅ MIT licensed with presets for minions, NPCs, and bosses

The repo has 345 stars and ships with calibration tests that prove the quality rulers work on your machine before you trust anything else.

Search GitHub for "Ariescar/anyCreature" and check the README.

What's the first creature you'd compile if you could type it into existence?
