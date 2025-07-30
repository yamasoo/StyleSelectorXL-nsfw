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


def read_sdxl_styles(json_data):
    if not isinstance(json_data, list):
        print("Error: input data must be a list")
        return None
    
    names = [item['name'] for item in json_data if isinstance(item, dict) and 'name' in item]
    names.sort()
    # 在名單前面加入 "Random Select" 選項
    names.insert(0, "Random Select")
    return names


def getStyles():
    global stylespath
    json_path = os.path.join(scripts.basedir(), 'nsfw_styles.json')
    stylespath = json_path
    json_data = get_json_content(json_path)
    return read_sdxl_styles(json_data)


def createPositive(style, positive):
    json_data = get_json_content(stylespath)
    try:
        if not isinstance(json_data, list):
            raise ValueError("Invalid JSON data. Expected a list of templates.")

        # 如果選擇了 "Random Select"，隨機選擇一個樣式
        if style == "Random Select":
            available_styles = [item['name'] for item in json_data if isinstance(item, dict) and 'name' in item]
            if available_styles:
                style = random.choice(available_styles)
            else:
                return positive  # 如果沒有可用樣式，返回原始提示

        for template in json_data:
            if template.get('name') == style:
                return template['prompt'].replace('{prompt}', positive)

        raise ValueError(f"No template found with name '{style}'.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


def createNegative(style, negative):
    json_data = get_json_content(stylespath)
    try:
        if not isinstance(json_data, list):
            raise ValueError("Invalid JSON data. Expected a list of templates.")

        # 如果選擇了 "Random Select"，隨機選擇一個樣式
        if style == "Random Select":
            available_styles = [item['name'] for item in json_data if isinstance(item, dict) and 'name' in item]
            if available_styles:
                style = random.choice(available_styles)
            else:
                return negative  # 如果沒有可用樣式，返回原始提示

        for template in json_data:
            if template.get('name') == style:
                json_negative_prompt = template.get('negative_prompt', "")
                return f"{json_negative_prompt}, {negative}" if json_negative_prompt and negative else json_negative_prompt or negative

        raise ValueError(f"No template found with name '{style}'.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        

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

def process_uploaded_json(file_obj):
    """處理上傳的JSON檔案"""
    global stylespath
    
    if file_obj is None:
        return None, None, "No file uploaded"
    
    try:
        # 讀取上傳的檔案內容
        if hasattr(file_obj, 'name'):
            file_path = file_obj.name
        else:
            file_path = str(file_obj)
            
        # 更新全域路徑
        stylespath = file_path
        
        # 載入JSON內容
        json_data = get_json_content(file_path)
        if json_data:
            new_styles = read_sdxl_styles(json_data)
            filename = os.path.basename(file_path)
            return new_styles, filename, f"Successfully loaded: {filename}"
        else:
            return None, None, f"Failed to parse JSON file: {os.path.basename(file_path)}"
            
    except Exception as e:
        print(f"Error processing uploaded file: {e}")
        return None, None, f"Error processing file: {str(e)}"


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


def update_styles_from_uploaded_file(file_obj):
    """從上傳的檔案更新樣式列表"""
    new_styles, filename, status = process_uploaded_json(file_obj)
    
    if new_styles:
        # 返回更新的下拉選單選項和狀態
        return (
            gr.Dropdown.update(choices=new_styles, value='base'),
            gr.Dropdown.update(choices=new_styles, value='base'),
            gr.Dropdown.update(choices=new_styles, value='base'),
            gr.Dropdown.update(choices=new_styles, value='base'),
            filename or "Unknown file",
            status
        )
    else:
        # 如果載入失敗，保持原狀
        return (
            gr.update(),
            gr.update(), 
            gr.update(),
            gr.update(),
            gr.update(),
            status or "File upload failed"
        )


def copy_styles_to_prompt_func(current_prompt, current_neg_prompt, style1, style2, style3, style4):
    """Copy selected non-base styles to prompt and reset styles to base"""
    current_prompt = current_prompt or ""
    current_neg_prompt = current_neg_prompt or ""
    
    # Collect non-base styles
    selected_styles = [s for s in [style1, style2, style3, style4] if s and s != 'base']
    
    if not selected_styles:
        return current_prompt, current_neg_prompt, 'base', 'base', 'base', 'base'
    
    # Get style prompts
    positive_styles = []
    negative_styles = []
    
    for style in selected_styles:
        try:
            pos_style = createPositive(style, "")
            neg_style = createNegative(style, "")
            
            if pos_style and pos_style.strip():
                positive_styles.append(pos_style.strip())
            if neg_style and neg_style.strip():
                negative_styles.append(neg_style.strip())
        except Exception as e:
            print(f"Error processing style {style}: {e}")
            continue
    
    # Combine styles with existing prompts
    new_prompt = current_prompt
    if positive_styles:
        style_text = ", ".join(positive_styles)
        if current_prompt.strip():
            new_prompt = f"{current_prompt}, {style_text}"
        else:
            new_prompt = style_text
            
    new_neg_prompt = current_neg_prompt
    if negative_styles:
        style_text = ", ".join(negative_styles)
        if current_neg_prompt.strip():
            new_neg_prompt = f"{current_neg_prompt}, {style_text}"
        else:
            new_neg_prompt = style_text
    
    # Return new prompts and reset all styles to 'base'
    return new_prompt, new_neg_prompt, 'base', 'base', 'base', 'base'


def add_to_main_prompt_func(current_prompt, current_neg_prompt, style_at_beginning):
    """Add current prompt texts to main A1111 prompt inputs"""
    # 這個函數會通過 JavaScript 來更新主要的提示輸入框
    # 由於我們無法直接訪問 A1111 的主要輸入框，這裡返回一個指示信息
    return f"Ready to add to main prompt:\nPositive: {current_prompt}\nNegative: {current_neg_prompt}\nPosition: {'Beginning' if style_at_beginning else 'End'}"


class StyleSelectorXL(scripts.Script):
    def __init__(self) -> None:
        super().__init__()
    
    styleNames = getStyles()

    def title(self):
        return "Style Selector for SDXL 1.0"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        enabled = getattr(shared.opts, "enable_styleselector_by_default", True)
        
        with gr.Group():
            with gr.Accordion("SDXL Styles", open=False):
                with FormRow():
                    with FormColumn(min_width=160):
                        is_enabled = gr.Checkbox(value=enabled, label="Enable Style Selector")
                    with FormColumn(elem_id="Style At Beginning"):
                        style_at_beginning = gr.Checkbox(value=False, label="Place Style At Beginning")

                with FormRow():
                    with FormColumn(min_width=160):
                        allstyles = gr.Checkbox(value=False, label="Generate All Styles In Order")

                with FormRow():
                    with FormColumn(min_width=160):
                        style1 = gr.Dropdown(self.styleNames, value='base', multiselect=False, label="Style 1")
                    with FormColumn(min_width=160):
                        style2 = gr.Dropdown(self.styleNames, value='base', multiselect=False, label="Style 2")
                    with FormColumn(min_width=160):
                        style3 = gr.Dropdown(self.styleNames, value='base', multiselect=False, label="Style 3")
                    with FormColumn(min_width=160):
                        style4 = gr.Dropdown(self.styleNames, value='base', multiselect=False, label="Style 4")

                # JSON file selection section
                gr.Markdown("### Style File Management")
                with FormRow():
                    with FormColumn(min_width=300):
                        json_file_upload = gr.File(
                            label="Upload JSON Style File", 
                            file_types=[".json"],
                            file_count="single"
                        )
                    with FormColumn(min_width=200):
                        open_button = gr.Button(value="Open Current JSON File", variant="secondary")
                    with FormColumn():
                        file_status = gr.Textbox(label="Current File", value="nsfw_styles.json", interactive=False)
                        
                with FormRow():
                    upload_status = gr.Textbox(label="Upload Status", lines=1, interactive=False)

                # Copy styles section
                gr.Markdown("### Copy Styles to Prompt")
                with FormRow():
                    with FormColumn():
                        prompt_preview = gr.Textbox(label="Current Prompt", placeholder="Enter your prompt here", lines=2)
                    with FormColumn():
                        neg_prompt_preview = gr.Textbox(label="Current Negative Prompt", placeholder="Enter your negative prompt here", lines=2)
                        
                with FormRow():
                    with FormColumn(min_width=160):
                        use_current_prompt = gr.Checkbox(value=False, label="Use Current Prompt as Style")
                    with FormColumn(min_width=200):
                        copy_styles_button = gr.Button(value="Copy Styles to Prompt & Reset to Base", variant="secondary")
                    with FormColumn(min_width=200):
                        add_to_main_button = gr.Button(value="Add to Main Prompt", variant="primary")
                        
                # Status display for add to main prompt
                with FormRow():
                    status_display = gr.Textbox(label="Status", lines=3, interactive=False)
                        
                # Set up JSON file upload functionality
                json_file_upload.change(
                    fn=update_styles_from_uploaded_file,
                    inputs=[json_file_upload],
                    outputs=[style1, style2, style3, style4, file_status, upload_status]
                )
                
                # Set up open JSON file functionality
                open_button.click(
                    fn=lambda: open_json_file(),
                    inputs=[],
                    outputs=[]
                )
                        
                # Set up the copy button functionality
                copy_styles_button.click(
                    fn=copy_styles_to_prompt_func,
                    inputs=[prompt_preview, neg_prompt_preview, style1, style2, style3, style4],
                    outputs=[prompt_preview, neg_prompt_preview, style1, style2, style3, style4]
                )
                
                # Set up the add to main prompt functionality
                add_to_main_button.click(
                    fn=add_to_main_prompt_func,
                    inputs=[prompt_preview, neg_prompt_preview, style_at_beginning],
                    outputs=[status_display]
                )
                
                # Add JavaScript to handle adding to main prompt
                add_to_main_button.click(
                    fn=None,
                    inputs=[prompt_preview, neg_prompt_preview, style_at_beginning],
                    outputs=[],
                    _js="""
                    function(current_prompt, current_neg_prompt, at_beginning) {
                        // 尋找主要的提示輸入框
                        const mainPromptInput = document.querySelector('#txt2img_prompt textarea, #img2img_prompt textarea');
                        const mainNegPromptInput = document.querySelector('#txt2img_neg_prompt textarea, #img2img_neg_prompt textarea');
                        
                        if (mainPromptInput && current_prompt && current_prompt.trim()) {
                            const existingPrompt = mainPromptInput.value || '';
                            if (at_beginning) {
                                mainPromptInput.value = current_prompt + (existingPrompt ? ', ' + existingPrompt : '');
                            } else {
                                mainPromptInput.value = existingPrompt + (existingPrompt ? ', ' + current_prompt : current_prompt);
                            }
                            // 觸發 input 事件以確保 gradio 檢測到變化
                            mainPromptInput.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                        
                        if (mainNegPromptInput && current_neg_prompt && current_neg_prompt.trim()) {
                            const existingNegPrompt = mainNegPromptInput.value || '';
                            if (at_beginning) {
                                mainNegPromptInput.value = current_neg_prompt + (existingNegPrompt ? ', ' + existingNegPrompt : '');
                            } else {
                                mainNegPromptInput.value = existingNegPrompt + (existingNegPrompt ? ', ' + current_neg_prompt : current_neg_prompt);
                            }
                            // 觸發 input 事件以確保 gradio 檢測到變化
                            mainNegPromptInput.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                        
                        return [];
                    }
                    """
                )
                
        return [is_enabled, allstyles, style_at_beginning, use_current_prompt, prompt_preview, neg_prompt_preview, style1, style2, style3, style4, file_status, upload_status]


    def process(self, p, is_enabled, allstyles, style_at_beginning, use_current_prompt, current_prompt_text, current_neg_prompt_text, style1, style2, style3, style4, file_status, upload_status):
        if not is_enabled:
            return

        batchCount = len(p.all_prompts)

        # Gather selected styles
        selected_styles = [s for s in [style1, style2, style3, style4] if s]

        # Generate style sets per prompt
        styles_per_prompt = {}
        for i in range(batchCount):
            if allstyles:
                # Cycle through all styles one at a time
                # 過濾掉 "Random Select" 選項以獲得實際的樣式名稱
                actual_styles = [s for s in self.styleNames if s != "Random Select"]
                if actual_styles:
                    styles_per_prompt[i] = [actual_styles[i % len(actual_styles)]]
                    print(f"AllStyles mode - Image {i}: {styles_per_prompt[i]}")
                else:
                    styles_per_prompt[i] = selected_styles
            else:
                # Same selected styles for all prompts
                styles_per_prompt[i] = selected_styles
                print(f"Normal mode - Image {i}: {selected_styles}")
        
        print(f"Total batch count: {batchCount}")
        print(f"Available style names count: {len(self.styleNames) if self.styleNames else 0}")

        # Inject positive prompts
        for i, original_prompt in enumerate(p.all_prompts):
            styles = styles_per_prompt[i]
            injected_styles = [createPositive(s, "") for s in styles if s]
            injection_parts = []
            
            print(f"Processing prompt {i}: styles = {styles}")
            print(f"Injected styles for prompt {i}: {injected_styles}")
            
            # Add style prompts
            style_injection = ", ".join([s for s in injected_styles if s]).strip(", ")
            if style_injection:
                injection_parts.append(style_injection)
            
            # Add current prompt text if enabled
            if use_current_prompt and current_prompt_text and current_prompt_text.strip():
                injection_parts.append(current_prompt_text.strip())
            
            # Combine all injections
            injection = ", ".join(injection_parts)
            
            if injection:
                if style_at_beginning:
                    p.all_prompts[i] = f"{injection}, {original_prompt}"
                else:
                    p.all_prompts[i] = f"{original_prompt}, {injection}"
                print(f"Final prompt {i}: {p.all_prompts[i]}")
            else:
                p.all_prompts[i] = original_prompt
                print(f"No injection for prompt {i}: {p.all_prompts[i]}")

        # Inject negative prompts
        for i, original_prompt in enumerate(p.all_negative_prompts):
            styles = styles_per_prompt[i]
            injected_styles = [createNegative(s, "") for s in styles if s]
            injection_parts = []
            
            print(f"Processing negative prompt {i}: styles = {styles}")
            print(f"Injected negative styles for prompt {i}: {injected_styles}")
            
            # Add style prompts
            style_injection = ", ".join([s for s in injected_styles if s]).strip(", ")
            if style_injection:
                injection_parts.append(style_injection)
            
            # Add current negative prompt text if enabled
            if use_current_prompt and current_neg_prompt_text and current_neg_prompt_text.strip():
                injection_parts.append(current_neg_prompt_text.strip())
            
            # Combine all injections
            injection = ", ".join(injection_parts)
            
            if injection:
                if style_at_beginning:
                    p.all_negative_prompts[i] = f"{injection}, {original_prompt}"
                else:
                    p.all_negative_prompts[i] = f"{original_prompt}, {injection}"
                print(f"Final negative prompt {i}: {p.all_negative_prompts[i]}")
            else:
                p.all_negative_prompts[i] = original_prompt
                print(f"No negative injection for prompt {i}: {p.all_negative_prompts[i]}")

        # Metadata
        p.extra_generation_params.update({
            "Style Selector Enabled": True,
            "Style Selector AllStyles": allstyles,
            "Style Selector At Beginning": style_at_beginning,
            "Style Selector Use Current Prompt": use_current_prompt,
            "Style Selector Styles Used": ", ".join(selected_styles)
        })



def on_ui_settings():
    section = ("styleselector", "Style Selector")
    shared.opts.add_option("styles_ui", shared.OptionInfo(
        "select-list", "How should Style Names Rendered on UI", gr.Radio, {"choices": ["radio-buttons", "select-list"]}, section=section))
    
    shared.opts.add_option("enable_styleselector_by_default", shared.OptionInfo(True, "Enable Style Selector by default", gr.Checkbox, section=section))
    
script_callbacks.on_ui_settings(on_ui_settings)
