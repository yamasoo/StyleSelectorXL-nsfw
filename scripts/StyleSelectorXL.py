import contextlib
import gradio as gr
from modules import scripts, shared, script_callbacks
from modules.ui_components import FormRow, FormColumn, FormGroup, ToolButton
import json
import os
import random
import subprocess
import platform

stylespath = ""

def get_json_content(file_path):
    try:
        with open(file_path, 'rt', encoding="utf-8") as file:
            json_data = json.load(file)
            return json_data
    except Exception as e:
        print(f"A Problem occurred: {str(e)}")
        return None

def read_sdxl_styles(json_data):
    if not isinstance(json_data, list):
        print("Error: input data must be a list")
        return None
    
    names = [item['name'] for item in json_data if isinstance(item, dict) and 'name' in item]
    names.sort()
    names.insert(0, "random")  # Add "random" as the first option
    return names

def getStyles(json_file):
    global stylespath
    json_path = os.path.join(scripts.basedir(), json_file)
    stylespath = json_path
    json_data = get_json_content(json_path)
    if json_data:
        return read_sdxl_styles(json_data)
    return ["base", "random"]

def createPositive(style, positive, append_style):
    if style == "random":
        json_data = get_json_content(stylespath)
        if not json_data:
            return positive
        style = random.choice([item['name'] for item in json_data if isinstance(item, dict) and 'name' in item])
    
    json_data = get_json_content(stylespath)
    try:
        if not isinstance(json_data, list):
            raise ValueError("Invalid JSON data. Expected a list of templates.")

        for template in json_data:
            if template.get('name') == style:
                style_prompt = template['prompt'].replace('{prompt}', positive)
                return f"{style_prompt}, {positive}" if append_style else f"{positive}, {style_prompt}"
        return positive
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return positive

def createNegative(style, negative):
    if style == "random":
        json_data = get_json_content(stylespath)
        if not json_data:
            return negative
        style = random.choice([item['name'] for item in json_data if isinstance(item, dict) and 'name' in item])
    
    json_data = get_json_content(stylespath)
    try:
        if not isinstance(json_data, list):
            raise ValueError("Invalid JSON data. Expected a list of templates.")

        for template in json_data:
            if template.get('name') == style:
                json_negative_prompt = template.get('negative_prompt', "")
                return f"{json_negative_prompt}, {negative}" if json_negative_prompt and negative else json_negative_prompt or negative
        return negative
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return negative

def append_style_to_json(name, prompt, negative_prompt):
    global stylespath
    try:
        with open(stylespath, 'r+', encoding='utf-8') as f:
            styles = json.load(f)
            styles.append({
                "name": name,
                "prompt": prompt,
                "negative_prompt": negative_prompt
            })
            f.seek(0)
            json.dump(styles, f, indent=2)
            f.truncate()
    except Exception as e:
        print(f"Error saving style: {e}")

def open_json_file():
    global stylespath
    try:
        if platform.system() == "Windows":
            os.startfile(stylespath)
        elif platform.system() == "Darwin":
            subprocess.call(["open", stylespath])
        else:
            subprocess.call(["xdg-open", stylespath])
    except Exception as e:
        print(f"Could not open file: {e}")

def get_json_files():
    extension_dir = scripts.basedir()
    return [f for f in os.listdir(extension_dir) if f.endswith('.json')]

class StyleSelectorXL(scripts.Script):
    def __init__(self) -> None:
        super().__init__()
        self.styleNames = getStyles("sdxl_styles.json")  # Default JSON file

    def title(self):
        return "Style Selector for SDXL 1.0 (NSFW)"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        enabled = getattr(shared.opts, "enable_styleselector_by_default", True)
        with gr.Group():
            with gr.Accordion("SDXL Styles (NSFW)", open=enabled):
                with FormRow():
                    with FormColumn(min_width=160):
                        is_enabled = gr.Checkbox(value=enabled, label="Enable Style Selector")
                    with FormColumn(elem_id="Randomize Style"):
                        randomize = gr.Checkbox(value=False, label="Randomize Style")
                    with FormColumn(elem_id="Append Style"):
                        append_style = gr.Checkbox(value=False, label="Place Style at End")

                with FormRow():
                    with FormColumn(min_width=160):
                        json_file = gr.Dropdown(get_json_files(), value='sdxl_styles.json', label="Style JSON File")
                        json_file.change(
                            fn=lambda x: getStyles(x),
                            inputs=[json_file],
                            outputs=[style1, style2, style3, style4]
                        )

                with FormRow():
                    with FormColumn(min_width=160):
                        style1 = gr.Dropdown(self.styleNames, value='base', multiselect=False, label="Style 1")
                    with FormColumn(min_width=160):
                        style2 = gr.Dropdown(self.styleNames, value='base', multiselect=False, label="Style 2")
                    with FormColumn(min_width=160):
                        style3 = gr.Dropdown(self.styleNames, value='base', multiselect=False, label="Style 3")
                    with FormColumn(min_width=160):
                        style4 = gr.Dropdown(self.styleNames, value='base', multiselect=False, label="Style 4")

                with FormRow():
                    with FormColumn(min_width=160):
                        append_to_prompt = gr.Button(value="Append Styles to Prompt")
                        append_to_prompt.click(
                            fn=self.append_styles_to_prompt,
                            inputs=[style1, style2, style3, style4, append_style],
                            outputs=[gr.State(), gr.State()]  # Outputs to WebUI prompt and negative prompt
                        )
                    with FormColumn(min_width=160):
                        open_button = gr.Button(value="Open JSON File")
                        open_button.click(
                            fn=lambda: open_json_file(),
                            inputs=[],
                            outputs=[]
                        )

                gr.Markdown("### Create New Style (Requires Restart)")
                
                with FormRow():
                    with FormColumn():
                        new_style_name = gr.Textbox(label="New Style Name:")
                        new_style_prompt = gr.Textbox(label="Positive Prompt:")
                        new_style_negative = gr.Textbox(label="Negative Prompt:")
                        
                with FormRow():
                    with FormColumn(min_width=160):
                        save_button = gr.Button(value="Save New Style")
                        save_button.click(
                            fn=lambda name, prompt, negative: (
                                append_style_to_json(name, prompt, negative),
                                "", "", ""
                            )[1:],
                            inputs=[new_style_name, new_style_prompt, new_style_negative],
                            outputs=[new_style_name, new_style_prompt, new_style_negative]
                        )

        return [is_enabled, randomize, append_style, json_file, style1, style2, style3, style4]

    def append_styles_to_prompt(self, style1, style2, style3, style4, append_style):
        selected_styles = [s for s in [style1, style2, style3, style4] if s and s != "base"]
        if not selected_styles:
            return "", ""

        positive_injection = []
        negative_injection = []
        for style in selected_styles:
            style_positive = createPositive(style, "", append_style)
            style_negative = createNegative(style, "")
            if style_positive:
                positive_injection.append(style_positive)
            if style_negative:
                negative_injection.append(style_negative)

        positive_result = ", ".join(positive_injection).strip(", ")
        negative_result = ", ".join(negative_injection).strip(", ")
        return positive_result, negative_result

    def process(self, p, is_enabled, randomize, append_style, json_file, style1, style2, style3, style4):
        if not is_enabled:
            return

        # Update styles if JSON file changes
        self.styleNames = getStyles(json_file)

        batchCount = len(p.all_prompts)
        selected_styles = [s for s in [style1, style2, style3, style4] if s]

        # Handle randomization
        if randomize:
            selected_styles = random.sample(self.styleNames, k=min(len(self.styleNames), 4))
            if "random" in selected_styles:
                selected_styles.remove("random")

        # Generate style sets per prompt
        styles_per_prompt = {}
        for i in range(batchCount):
            styles_per_prompt[i] = selected_styles

        # Inject positive prompts
        for i, original_prompt in enumerate(p.all_prompts):
            styles = styles_per_prompt[i]
            injected_styles = [createPositive(s, original_prompt, append_style) for s in styles]
            injection = ", ".join([s for s in injected_styles if s]).strip(", ")
            p.all_prompts[i] = injection if injection else original_prompt

        # Inject negative prompts
        for i, original_negative in enumerate(p.all_negative_prompts):
            styles = styles_per_prompt[i]
            injected_styles = [createNegative(s, original_negative) for s in styles]
            injection = ", ".join([s for s in injected_styles if s]).strip(", ")
            p.all_negative_prompts[i] = injection if injection else original_negative

        # Metadata
        p.extra_generation_params.update({
            "Style Selector Enabled": True,
            "Style Selector Randomize": randomize,
            "Style Selector Append": append_style,
            "Style Selector JSON File": json_file,
            "Style Selector Styles Used": ", ".join(selected_styles)
        })

def on_ui_settings():
    section = ("styleselector_nsfw", "Style Selector (NSFW)")
    shared.opts.add_option("enable_styleselector_by_default", shared.OptionInfo(
        True, "Enable Style Selector by default", gr.Checkbox, section=section))

script_callbacks.on_ui_settings(on_ui_settings)