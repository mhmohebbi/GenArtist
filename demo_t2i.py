from PIL import Image
import os
import os.path as osp
import torch
import diffusers
import cv2
# from agent_tool_aux import main_aux
# from agent_tool_edit import main_edit
# from agent_tool_generate import main_generate
import gc
import json
from openai import OpenAI
import requests
import base64

# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def command_parse(commands, text, text_bg, dir='inputs'):
    args = []
    generation_arg = None
    for i in range(len(commands)):
        command = commands[i]
        if command['tool'] == 'edit':
            k = len(args)
            if 'box' in command:
                if 'intbox' in command:
                    bb = command['box']
                    command['box'] = [bb[0]/512., bb[1]/512., (bb[2]-bb[0])/512., (bb[3]-bb[1])/512.]
                arg = {"tool": "segmentation", "output": osp.join(dir, str(k+1)+'_mask.png'), "input": {"image": osp.join(dir, str(k)+'.png'), "text": command["input"], 'box': command['box']} }
            else:
                arg = {"tool": "segmentation", "output": osp.join(dir, str(k+1)+'_mask.png'), "input": {"image": osp.join(dir, str(k)+'.png'), "text": command["input"]} }
            args.append(arg)

            arg = {"tool": "object_addition_anydoor",  "text": text, "text_bg": text_bg, 
                    "output": osp.join(dir, str(k+2)+'.png'), "output_mask": osp.join(dir, str(k+2)+'_mask.png'), 
                    "input": {"image": osp.join(dir, str(k)+'.png'), "object": command["edit"], "layout": osp.join(dir, str(k+1)+'_mask.png') } }
            args.append(arg)

            arg = {"tool": "replace_anydoor", "output": osp.join(dir, str(k+3)+'.png'), 
                    "input": {"image": osp.join(dir, str(k)+'.png'), "object": osp.join(dir, str(k+2)+'.png'),
                             "object_mask": osp.join(dir, str(k+2)+'_mask.png'), "mask": osp.join(dir, str(k+1)+'_mask.png'),  } }
            args.append(arg)
        elif command['tool'] == 'move':
            if 'intbox' in command:
                bb = command['box']
                command['box'] = [bb[0]/512., bb[1]/512., (bb[2]-bb[0])/512., (bb[3]-bb[1])/512.]
            k = len(args)
            arg = {"tool": "segmentation", "output": osp.join(dir, str(k+1)+'_mask.png'), "input": {"image": osp.join(dir, str(k)+'.png'), "text": command["input"]} }
            args.append(arg)

            arg = {"tool": "remove", "output":  osp.join(dir, str(k+2)+'.png'), "input": {"image": osp.join(dir, str(k)+'.png'), "mask": osp.join(dir, str(k+1)+'_mask.png')} }
            args.append(arg)

            arg = {"tool": "addition_anydoor", "output": osp.join(dir, str(k+3)+'.png'), 
                "input": {"image": osp.join(dir, str(k+2)+'.png'), "object": osp.join(dir, str(k)+'.png'), 
                        "object_mask": osp.join(dir, str(k+1)+'_mask.png'), "mask": command["box"]  } }
            args.append(arg)
        elif command['tool'] == 'addition':
            k = len(args)
            if 'intbox' in command:
                bb = command['box']
                command['box'] = [bb[0]/512., bb[1]/512., (bb[2]-bb[0])/512., (bb[3]-bb[1])/512.]
            arg = {"tool": "object_addition_anydoor",  "text": text, "text_bg": text_bg, 
                    "output": osp.join(dir, str(k+1)+'.png'), "output_mask": osp.join(dir, str(k+1)+'_mask.png'), 
                    "input": {"image": osp.join(dir, str(k)+'.png'), "object": command["input"], "layout": command["box"] } }
            args.append(arg)

            arg = {"tool": "addition_anydoor", "output": osp.join(dir, str(k+2)+'.png'), 
                "input": {"image": osp.join(dir, str(k)+'.png'), "object": osp.join(dir, str(k+1)+'.png'), 
                        "object_mask": osp.join(dir, str(k+1)+'_mask.png'), "mask": command["box"]  } }
            args.append(arg)
        elif command['tool'] == 'remove':
            k = len(args)
            arg = {"tool": "segmentation", "output": osp.join(dir, str(k+1)+'_mask.png'), "input": {"image": osp.join(dir, str(k)+'.png'), "text": command["input"], "mask_threshold": command.get("mask_thr", 0.0)} }
            if 'box' in command:
                if 'intbox' in command:
                    bb = command['box']
                    command['box'] = [bb[0]/512., bb[1]/512., (bb[2]-bb[0])/512., (bb[3]-bb[1])/512.]
                arg['input']['box'] = command['box']
            args.append(arg)

            arg = {"tool": "remove", "output":  osp.join(dir, str(k+2)+'.png'), "input": {"image": osp.join(dir, str(k)+'.png'), "mask": osp.join(dir, str(k+1)+'_mask.png')} }
            args.append(arg)
        elif command['tool'] == 'instruction':
            k = len(args)
            print("The text for instruction tool is ", command["text"])
            arg = {"tool": "instruction", "output": osp.join(dir, str(k+1)+'.png'), "input": {"image": osp.join(dir, str(k)+'.png'), "text": command["text"]} }
            args.append(arg)
        elif command['tool'] == 'edit_attribute':
            k = len(args)
            if 'box' in command:
                arg = {"tool": "segmentation", "output": osp.join(dir, str(k+1)+'_mask.png'), "input": {"image": osp.join(dir, str(k)+'.png'), "text": command["input"], 'box': command['box']} }
            else:
                arg = {"tool": "segmentation", "output": osp.join(dir, str(k+1)+'_mask.png'), "input": {"image": osp.join(dir, str(k)+'.png'), "text": command["input"]} }
            args.append(arg)

            arg = {"tool": "attribute_diffedit", 
                    "output": osp.join(dir, str(k+2)+'.png'),  
                    "input": {"image": osp.join(dir, str(k)+'.png'), "object": command["input"], "object_mask": osp.join(dir, str(k+1)+'_mask.png'), "attr": command["text"] } }
            args.append(arg)
        
        elif command['tool'] in ['text_to_image_SDXL', 'image_to_image_SD2', 'layout_to_image_LMD', 'layout_to_image_BoxDiff', 'superresolution_SDXL']:
            generation_arg = command
            generation_arg["output"] = osp.join(dir, '0.png')
    
    k = len(args)
    arg = {"tool": "superresolution_SDXL", "input": {"image": osp.join(dir, str(k)+'.png')}, "output": osp.join(dir, str(k+1)+'.png')}
    args.append(arg)
    if generation_arg is not None:
        args = [generation_arg] + args
    return args



if __name__ == '__main__':
    # prompt = 'an oil painting, where a green vintage car, a black scooter on the left of it and a blue bicycle on the right of it, are parked near a curb, with three birds in the sky'
    prompt = "Two hot dogs sit on a green plate near a soda cup which are sitting on a white picnic table, while a red bike on the right of a blue car are parked nearby."

    # prompt = "An icy landscape. A vast expanse of snow-covered mountain peaks stretches endlessly. Beneath them is a dense forest and a colossal frozen lake. Three people are boating in three boats separately in the lake. Not far from the lake, a volcano threatens eruption, its rumblings felt even from afar. Above, a ferocious red dragon dominates the sky and commands the heavens, fueled by the volcano's relentless energy flow."
    api_key = os.getenv("OPENAI_API_KEY", "your-api-key-here")

    url = "https://api.openai.com/v1/chat/completions"
    client = OpenAI(api_key=api_key)
    print("API key loaded")
    with open('prompts/generation.txt', 'r', encoding='utf-8') as f:
        template=f.readlines()
    user_textprompt=f"Input: {prompt}"
    
    textprompt= f"{' '.join(template)} \n {user_textprompt}"
    
    payload = json.dumps({
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": textprompt
            }
        ]
        })
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {api_key}',
        'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
        'Content-Type': 'application/json'
        }
    print('waiting for GPT-4 response in generation model selection')
    response = requests.request("POST", url, headers=headers, data=payload)
    obj = response.json()
    gen_text = obj['choices'][0]['message']['content']
    json.dump(gen_text, open('gen_text.json','w'))

    gen_text = json.load(open('gen_text.json'))
    gen_text = eval(gen_text)
    # print(gen_text, type(gen_text))


    with open('prompts/bbox.txt', 'r', encoding='utf-8') as f:
        template=f.readlines()
    user_textprompt=f"Caption: {prompt}"

    textprompt= f"{' '.join(template)} \n {user_textprompt}"
    payload = json.dumps({
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": textprompt
            }
        ]
        })
    print('waiting for GPT-4 response in bounding box generation')
    response = requests.request("POST", url, headers=headers, data=payload)
    obj = response.json()
    bbox_text = obj['choices'][0]['message']['content']
    # print(bbox_text)
    json.dump(bbox_text, open('bbox_text.json','w'))

    bbox_text = json.load(open('bbox_text.json'))
    bbox_text = eval(bbox_text)
    # print(bbox_text, type(bbox_text))
    gen_text['input']['layout'] = bbox_text['layout']
    gen_text['input']['bg_prompt'] = bbox_text['bg_prompt']


    ## generation and detection
    generation_command = [gen_text]
    print("The generation command is:\n", generation_command)
    seq_args = command_parse(generation_command, prompt, gen_text['input']['bg_prompt'])
    seq_args = [seq_args[0], {'tool':'detection', 'input':{'image':'inputs/0.png', 'text':'TBG'}}]
    json.dump(seq_args[0], open('input.json','w'))
    os.system('python agent_tool_generate.py --json_out True')
    json.dump(seq_args[1], open('input.json','w'))
    os.system('python agent_tool_aux.py --json_out True')


    ## verification and self-correction

    with open('prompts/correction.txt', 'r', encoding='utf-8') as f:
        template=f.readlines()
    user_textprompt = f"Caption: {prompt}\n"
    detection_results = json.load(open('input_detection.json'))
    user_textprompt += 'I can give you the position of all objects in the image: ' + str(detection_results) + '\n'
    user_textprompt += 'You can use these as a reference for generating the bounding box position of objects'
    user_textprompt += 'Please onlyoutput the editing operations through dict, do not output other analysis process. Return the result with only plain text, do not use any markdown or other style. All characters must be in English.'
    
    textprompt= f"{' '.join(template)} \n {user_textprompt}"
    image_path = "inputs/0.png"
    base64_image = encode_image(image_path)
    payload = json.dumps({
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [{'type':'text', 'text':textprompt}, {'type':'image_url', 'image_url':{"url":  f"data:image/jpeg;base64,{base64_image}"} }]
            }
        ]
        })
    print('waiting for GPT-4 response in verification and self-correction')
    response = requests.request("POST", url, headers=headers, data=payload)
    obj = response.json()
    correction_text = obj['choices'][0]['message']['content']
    # print(correction_text)
    json.dump(correction_text, open('correction_text.json','w'))

    correction_text = json.load(open('correction_text.json'))
    
    # Handle double-encoded JSON string
    try:
        # First try to parse as a single JSON object
        if isinstance(correction_text, str):
            correction_text = json.loads(correction_text)
        correction_text = eval(correction_text) if isinstance(correction_text, str) else correction_text
    except:
        # If that fails, split by actual newlines and parse each JSON object
        # Handle escaped newlines in the string
        if isinstance(correction_text, str):
            if '\\n' in correction_text:
                lines = correction_text.split('\\n')
            else:
                lines = correction_text.split('\n')
            
            correction_text = []
            for line in lines:
                line = line.strip()
                if line:
                    try:
                        correction_text.append(json.loads(line))
                    except:
                        print(f"Failed to parse line: {line}")
                        continue
    
    # Fix correction commands that don't have required keys
    if isinstance(correction_text, dict):
        if 'tool' not in correction_text:
            # Infer tool type based on available keys
            if 'edit' in correction_text and 'input' in correction_text:
                correction_text['tool'] = 'instruction'
                correction_text['text'] = correction_text.get('instruction', correction_text.get('edit', ''))
            elif 'input' in correction_text and not correction_text.get('edit'):
                correction_text['tool'] = 'remove'
        elif correction_text['tool'] == 'instruction' and 'text' not in correction_text:
            # For instruction commands, map 'input' to 'text' if 'text' is missing
            correction_text['text'] = correction_text.get('input', '')
    elif isinstance(correction_text, list):
        for cmd in correction_text:
            if isinstance(cmd, dict):
                if 'tool' not in cmd:
                    if 'edit' in cmd and 'input' in cmd:
                        cmd['tool'] = 'instruction'
                        cmd['text'] = cmd.get('instruction', cmd.get('edit', ''))
                    elif 'input' in cmd and not cmd.get('edit'):
                        cmd['tool'] = 'remove'
                elif cmd['tool'] == 'instruction' and 'text' not in cmd:
                    # For instruction commands, map 'input' to 'text' if 'text' is missing
                    cmd['text'] = cmd.get('input', '')
    
    if type(correction_text) is list:
        commands = [gen_text] + correction_text
    else:
        commands = [gen_text, correction_text]
    print("The commands are:\n", commands)
    seq_args = command_parse(commands, prompt, gen_text['input']['bg_prompt'])

    print('----------------------------------------------')
    for i in range(len(seq_args)):
        print(i, seq_args[i])


    print('----------------------------------------------')
    print("Now start the generation process")

    for i in range(1, len(seq_args)):
        json.dump(seq_args[i], open('input.json','w'))
        if seq_args[i]['tool'] in ["object_addition_anydoor", "segmentation"]:
            # main_aux(seq_args[i])
            os.system('python agent_tool_aux.py --json_out True')
        elif seq_args[i]['tool'] in ["addition_anydoor", "replace_anydoor", "remove", "instruction", "attribute_diffedit"]:
            # main_edit(seq_args[i])
            os.system('python agent_tool_edit.py --json_out True')
        elif seq_args[i]['tool'] in ['text_to_image_SDXL', 'image_to_image_SD2', 'layout_to_image_LMD', 'layout_to_image_BoxDiff', 'superresolution_SDXL']:
            # main_generate(seq_args[i])
            os.system('python agent_tool_generate.py --json_out True')
