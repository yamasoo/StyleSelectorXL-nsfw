"""All Styles integration for ``sdxl_styles.py``.

Automatic1111 imports every Python file in ``scripts``.  This module patches the
existing StyleSelectorXL class at import time, so the batch logic is part of the
running ``sdxl_styles.py`` script rather than a second visible extension.
"""

from __future__ import annotations

import importlib


def _load_target():
    # Depending on how Automatic1111 loads extensions, the same file can be
    # registered as either ``sdxl_styles`` or ``scripts.sdxl_styles``.
    for module_name in ("sdxl_styles", "scripts.sdxl_styles"):
        try:
            return importlib.import_module(module_name)
        except ImportError:
            continue
    return None


def _install_patch():
    target = _load_target()
    if target is None or not hasattr(target, "StyleSelectorXL"):
        return

    cls = target.StyleSelectorXL
    if getattr(cls, "_allstyles_batch_update_installed", False):
        return

    def _auto_expand_batch(p, needed):
        """Expand all generation arrays to fit one image per style."""
        batch_size = max(1, int(getattr(p, "batch_size", 1) or 1))
        new_n_iter = max(1, -(-needed // batch_size))
        total = new_n_iter * batch_size
        prompts = list(getattr(p, "all_prompts", []) or [])

        if total == len(prompts) and getattr(p, "n_iter", 1) == new_n_iter:
            return

        p.n_iter = new_n_iter
        prompt_seed = prompts[0] if prompts else ""

        def _fit(values, fallback):
            if values is None:
                return None
            values = list(values)
            if len(values) > total:
                return values[:total]
            while len(values) < total:
                values.append(fallback(len(values)))
            return values

        p.all_prompts = _fit(prompts, lambda _: prompt_seed)

        negatives = getattr(p, "all_negative_prompts", None)
        if negatives is not None:
            negatives = list(negatives)
            negative_seed = negatives[0] if negatives else ""
            p.all_negative_prompts = _fit(negatives, lambda _: negative_seed)

        seeds = getattr(p, "all_seeds", None)
        if seeds is not None:
            seeds = list(seeds)
            seed = int(seeds[0]) if seeds else -1
            step = 1 if getattr(p, "subseed_strength", 0) == 0 else 0
            p.all_seeds = (
                [seed + index * step for index in range(total)]
                if step else _fit(seeds, lambda _: seed)
            )

        subseeds = getattr(p, "all_subseeds", None)
        if subseeds is not None:
            subseeds = list(subseeds)
            seed = int(subseeds[0]) if subseeds else -1
            p.all_subseeds = _fit(subseeds, lambda index: seed + index)

        try:
            target.shared.state.job_count = new_n_iter
        except Exception:
            pass

        print(
            f"[StyleSelector] AllStyles: batch count auto-set to "
            f"{new_n_iter} (batch size {batch_size}, {needed} styles)"
        )

    original_process = cls.process

    def process(self, p, is_enabled, allstyles, *args, **kwargs):
        if is_enabled and allstyles:
            json_data = target.get_json_content(target.stylespath)
            categories = args[8:12] if len(args) >= 12 else ()
            active_categories = sorted({
                category for category in categories
                if category and category != "ALL"
            })

            pool = []
            if active_categories and isinstance(json_data, list):
                seen = set()
                for category in active_categories:
                    for item in target.filter_styles_by_category(json_data, category):
                        name = item.get("name") if isinstance(item, dict) else None
                        if name and name not in seen:
                            seen.add(name)
                            pool.append(name)
                pool.sort()

            if not pool:
                pool = [
                    name for name in cls.styleNames
                    if name not in ("base", "Random Select")
                ]

            if pool:
                _auto_expand_batch(p, len(pool))

        result = original_process(self, p, is_enabled, allstyles, *args, **kwargs)
        # process_batch() uses this flag to update per-batch infotext.
        self.style_selector_allstyles = bool(allstyles)
        return result

    cls._auto_expand_batch = staticmethod(_auto_expand_batch)
    cls.process = process
    cls._allstyles_batch_update_installed = True


_install_patch()
