🚨 Your animator just quoted 6 weeks to hand-key a 30-second fight sequence.

Mocap suits cost $15K. Contractors charge $200/day. And every revision means another round trip through the keyframe swamp.

Mixamo LLM Mocap changes that math completely.

You film a performer throwing kicks — or generate AI footage with T-pose bookends — and ten Python stages turn it into clean FK animations on any Mixamo character you already own:

✅ GVHMR extracts mesh-quality joints from locked-camera video
✅ Direction-preserving retarget rebuilds positions from YOUR rig's bone lengths
✅ Real ground contact with zero foot skate — planted feet solve to ground height every frame

No manual keyframing. No IK (because Mixamo rigs are FK-only). No cleanup.

198 GitHub stars because the pipeline includes a QA gate that catches exploded bones, hip pops, and foot skate *before* a human looks. Every stage is scriptable enough that an AI agent can run the whole loop.

Two-character plates? Split tracks by screen side, retarget onto different proportions, place them at measured distances, then run mesh-vs-mesh collision to verify clearance.

Search "Mixamo LLM Mocap" on GitHub and clone it today.

What's the longest fight sequence you've hand-keyed? 💬
