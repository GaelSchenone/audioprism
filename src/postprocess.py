"""Bloom post-processing: bright-pass → separable gaussian blur → composite.

Brightness is measured *relative to the palette background*, so bloom only
glows ink that is brighter than the canvas. On dark themes the bars/particles
glow; on light themes (white background) nothing exceeds the background, so
bloom naturally fades out instead of washing the screen white.
"""

from __future__ import annotations

import moderngl

from src.presets.base import fullscreen_vao

_VERT = """
#version 330
in vec2 in_pos;
out vec2 v_uv;
void main() { v_uv = in_pos * 0.5 + 0.5; gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

_BRIGHT = """
#version 330
in vec2 v_uv; out vec4 frag;
uniform sampler2D scene;
uniform float bg_lum;
uniform float threshold;
void main() {
    vec3 c = texture(scene, v_uv).rgb;
    float lum = dot(c, vec3(0.2126, 0.7152, 0.0722));
    float b = max(0.0, lum - bg_lum);
    float w = smoothstep(threshold, threshold + 0.25, b);
    frag = vec4(c * w, 1.0);
}
"""

_BLUR = """
#version 330
in vec2 v_uv; out vec4 frag;
uniform sampler2D tex;
uniform vec2 direction;        // texel step along blur axis
void main() {
    vec3 sum = texture(tex, v_uv).rgb * 0.2270270270;
    vec2 o1 = direction * 1.3846153846;
    vec2 o2 = direction * 3.2307692308;
    sum += texture(tex, v_uv + o1).rgb * 0.3162162162;
    sum += texture(tex, v_uv - o1).rgb * 0.3162162162;
    sum += texture(tex, v_uv + o2).rgb * 0.0702702703;
    sum += texture(tex, v_uv - o2).rgb * 0.0702702703;
    frag = vec4(sum, 1.0);
}
"""

_COMPOSITE = """
#version 330
in vec2 v_uv; out vec4 frag;
uniform sampler2D scene;
uniform sampler2D bloom;
uniform float intensity;
void main() {
    vec3 c = texture(scene, v_uv).rgb;
    vec3 b = texture(bloom, v_uv).rgb;
    frag = vec4(c + b * intensity, 1.0);
}
"""


class PostProcess:
    THRESHOLD = 0.12
    ITERATIONS = 3

    def __init__(self, ctx: moderngl.Context, size: tuple[int, int]) -> None:
        self.ctx = ctx
        self.brightpass = ctx.program(vertex_shader=_VERT, fragment_shader=_BRIGHT)
        self.blur = ctx.program(vertex_shader=_VERT, fragment_shader=_BLUR)
        self.composite = ctx.program(vertex_shader=_VERT, fragment_shader=_COMPOSITE)
        self.vao_bright = fullscreen_vao(ctx, self.brightpass)
        self.vao_blur = fullscreen_vao(ctx, self.blur)
        self.vao_comp = fullscreen_vao(ctx, self.composite)
        self._build(size)

    def _build(self, size: tuple[int, int]) -> None:
        self.w, self.h = size
        bw, bh = max(1, self.w // 2), max(1, self.h // 2)
        self.bw, self.bh = bw, bh
        self.tex_a = self.ctx.texture((bw, bh), 3, dtype="f2")
        self.tex_b = self.ctx.texture((bw, bh), 3, dtype="f2")
        for t in (self.tex_a, self.tex_b):
            t.filter = (moderngl.LINEAR, moderngl.LINEAR)
            t.repeat_x = t.repeat_y = False
        self.fbo_a = self.ctx.framebuffer(color_attachments=[self.tex_a])
        self.fbo_b = self.ctx.framebuffer(color_attachments=[self.tex_b])

    def resize(self, size: tuple[int, int]) -> None:
        if size == (self.w, self.h):
            return
        for obj in (self.fbo_a, self.fbo_b, self.tex_a, self.tex_b):
            obj.release()
        self._build(size)

    def run(
        self,
        scene_tex: moderngl.Texture,
        target_fbo: moderngl.Framebuffer,
        intensity: float,
        bg_lum: float,
    ) -> None:
        # Bright-pass: scene → half-res tex_a
        self.fbo_a.use()
        self.ctx.viewport = (0, 0, self.bw, self.bh)
        scene_tex.use(0)
        self.brightpass["scene"] = 0
        self.brightpass["bg_lum"] = bg_lum
        self.brightpass["threshold"] = self.THRESHOLD
        self.vao_bright.render(moderngl.TRIANGLES)

        # Separable gaussian blur, ping-ponging a↔b
        for _ in range(self.ITERATIONS):
            self.fbo_b.use()
            self.tex_a.use(0)
            self.blur["tex"] = 0
            self.blur["direction"] = (1.0 / self.bw, 0.0)
            self.vao_blur.render(moderngl.TRIANGLES)

            self.fbo_a.use()
            self.tex_b.use(0)
            self.blur["tex"] = 0
            self.blur["direction"] = (0.0, 1.0 / self.bh)
            self.vao_blur.render(moderngl.TRIANGLES)

        # Composite scene + bloom → full-res target
        target_fbo.use()
        self.ctx.viewport = (0, 0, self.w, self.h)
        scene_tex.use(0)
        self.tex_a.use(1)
        self.composite["scene"] = 0
        self.composite["bloom"] = 1
        self.composite["intensity"] = intensity
        self.vao_comp.render(moderngl.TRIANGLES)

    def release(self) -> None:
        for obj in (self.fbo_a, self.fbo_b, self.tex_a, self.tex_b,
                    self.vao_bright, self.vao_blur, self.vao_comp,
                    self.brightpass, self.blur, self.composite):
            obj.release()
