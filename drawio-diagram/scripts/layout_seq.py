"""Sequence layout: participants as columns + time-slotted messages + frames.

Structurally different from architecture/flowchart — participants are COLUMNS,
messages are horizontal arrows at increasing y time-slots, lifelines/frames are
decorations. Messages are free-floating edges (no source/target vertex): they
attach to lifelines at the message y, not to the header boxes at the top.

Algorithm (deterministic):
  * Participants -> evenly spaced columns at cx_i = MARGIN + i*COL_W where
    COL_W = snap(widest_label_pw + GUTTER_X) (generous: headers never crowd).
    Each participant gets a header box at the top row (a real node).
  * A lifeline decoration per participant: vertical dashed line from just below
    the header box to the canvas bottom margin.
  * Messages -> horizontal arrows stacked strictly in list order:
    msg_y_k = msg_y_0 + k*MSG_GAP. flow = "async" if dashed else "data".
    Self-messages (from==to) loop out the right side and back.
  * Frames (optional loop/alt) -> rect decorations spanning the message
    y-range [from..to] (1-based message indexes per the schema).

All geometry goes through layout.assert_invariants before return.
The input diagram is never mutated.
"""
import layout

NODE_H = layout.NODE_H
MSG_GAP = 60
SELF_LOOP_W = 40      # how far a self-message sticks out to the right
SELF_LOOP_H = 20      # vertical drop of a self-message loop
FRAME_PAD = 10        # padding around a frame's message y-range
LIFELINE_W = 0        # lifeline is a line (width 0); renderer special-cases it


def layout_sequence(d: dict) -> dict:
    geom = layout.empty_geometry("sequence", d["style"], d["title"])
    participants = d["participants"]
    messages = d.get("messages", [])
    frames = d.get("frames", [])

    # --- column geometry ---------------------------------------------------
    # Header widths first: snap up to a multiple of (2*SNAP) so w//2 is itself
    # snapped, which keeps every header's geometric center exactly on its
    # column center (uniform spacing) and x on the SNAP grid.
    widths = []
    for p in participants:
        tw = layout.text_width(p["label"])
        w = tw if tw % (2 * layout.SNAP) == 0 else tw + (2 * layout.SNAP - tw % (2 * layout.SNAP))
        widths.append(w)
    max_half = max((w // 2 for w in widths), default=0)

    widest_pw = max((layout.text_width(p["label"]) for p in participants),
                    default=layout.NODE_MIN_W)
    col_w = layout.snap(max(layout.GUTTER_X * 3 // 2, widest_pw + layout.GUTTER_X))
    # First column center leaves room for the widest header's left half so no
    # header ever starts at a negative x (in-bounds invariant).
    left_pad = layout.snap(max(layout.MARGIN, max_half + layout.MIN_GAP))

    centers: dict[str, tuple[int, int]] = {}  # id -> (cx, header_right_x)
    for i, p in enumerate(participants):
        cx = layout.snap(left_pad + i * col_w)
        w = widths[i]
        x = cx - w // 2
        y = layout.MARGIN
        h = layout.snap(NODE_H)
        geom["nodes"].append({
            "id": p["id"], "label": p["label"],
            "kind": p.get("kind", "service"),
            "x": x, "y": y, "width": w, "height": h,
        })
        centers[p["id"]] = (cx, x, w)

    last_cx, _, last_w = centers[participants[-1]["id"]]
    last_col_right = last_cx + last_w // 2
    canvas_w = layout.snap(last_col_right + layout.MARGIN)

    # --- message y-slots (time axis) --------------------------------------
    header_bottom = layout.MARGIN + NODE_H
    msg_y_0 = layout.snap(header_bottom + layout.GUTTER_Y)
    msg_ys = [layout.snap(msg_y_0 + k * MSG_GAP) for k in range(len(messages))]
    last_msg_y = msg_ys[-1] if msg_ys else header_bottom

    canvas_h = layout.snap(last_msg_y + MSG_GAP + layout.MARGIN)
    geom["canvas"] = {"width": canvas_w, "height": canvas_h}
    lifeline_bottom = canvas_h - layout.MARGIN

    # --- lifeline decorations (one per participant) -----------------------
    for p in participants:
        cx, _, _ = centers[p["id"]]
        geom["decorations"].append({
            "kind": "lifeline",
            "x": cx,
            "y": header_bottom,
            "width": LIFELINE_W,
            "height": max(0, lifeline_bottom - header_bottom),
            "label": p["id"],
        })

    # --- message edges (free-floating, attach to lifelines) ---------------
    for m, y in zip(messages, msg_ys):
        from_cx, _, _ = centers[m["from"]]
        to_cx, _, _ = centers[m["to"]]
        flow = "async" if m.get("dashed") else "data"
        if m["from"] == m["to"]:
            # self-message: small rect loop out the right side and back
            pts = [
                (from_cx, y),
                (from_cx + SELF_LOOP_W, y),
                (from_cx + SELF_LOOP_W, y + SELF_LOOP_H),
                (from_cx, y + SELF_LOOP_H),
            ]
        else:
            pts = [(from_cx, y), (to_cx, y)]
        geom["edges"].append({
            "label": m.get("label", ""),
            "flow": flow,
            "points": pts,
            "free": True,  # attach via points, not participant header vertices
        })

    # --- frame decorations (span message y-range) -------------------------
    for fr in frames:
        start_idx = fr.get("from", 1) - 1  # schema: 1-based message index
        end_idx = fr.get("to", start_idx + 1) - 1
        start_idx = max(0, min(start_idx, len(msg_ys) - 1))
        end_idx = max(0, min(end_idx, len(msg_ys) - 1))
        y_top = msg_ys[start_idx] - FRAME_PAD
        y_bot = msg_ys[end_idx] + FRAME_PAD
        fx = layout.snap(layout.MARGIN - FRAME_PAD)
        fw = layout.snap(canvas_w - 2 * (layout.MARGIN - FRAME_PAD))
        geom["decorations"].append({
            "kind": "frame",
            "x": max(0, fx),
            "y": max(0, layout.snap(y_top)),
            "width": fw,
            "height": layout.snap(y_bot - y_top),
            "label": fr.get("label", fr.get("kind", "")),
            "frame_kind": fr.get("kind", "frame"),
        })

    labels = {p["id"]: p["label"] for p in participants}
    layout.assert_invariants(geom, source_nodes=labels)
    return geom
