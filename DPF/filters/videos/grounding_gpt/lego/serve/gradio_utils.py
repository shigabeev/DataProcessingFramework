import torch
from lego.conversation import SeparatorStyle, conv_templates
from lego.mm_utils import (KeywordsStoppingCriteria, get_model_name_from_path,
                           tokenizer_image_token)
from lego.model.builder import load_pretrained_model
from lego.utils import disable_torch_init

IMAGE_TOKEN_INDEX = -200
title_markdown = ("""
<div style="display: flex; justify-content: center; align-items: center; text-align: center;">
  <div>
    <h1 >LEGO:Language-Enhanced Grounding Multi-modal Large Model</h1>
    <h5 style="margin: 0;">If you like our project, please give us a star ✨ on Github for the latest update.</h5>
  </div>
</div>
""")

block_css = """
#buttons button {
    min-width: min(120px,100%);
}
"""


tos_markdown = ("""
### Terms of use
By using this service, users are required to agree to the following terms:
The service is a research preview intended for non-commercial use only. It only provides limited safety measures and may generate offensive content. It must not be used for any illegal, harmful, violent, racist, or sexual purposes. The service may collect user dialogue data for future research.
Please click the "Flag" button if you get any inappropriate answer! We will collect those to keep improving our moderator.
For an optimal experience, please use desktop computers for this demo, as mobile devices may compromise its quality.
""")


learn_more_markdown = ("""
### License
The service is a research preview intended for non-commercial use only, subject to the model [License](https://github.com/facebookresearch/llama/blob/main/MODEL_CARD.md) of LLaMA, [Terms of Use](https://openai.com/policies/terms-of-use) of the data generated by OpenAI, and [Privacy Practices](https://chrome.google.com/webstore/detail/sharegpt-share-your-chatg/daiacboceoaocpibfodeljbdfacokfjb) of ShareGPT. Please contact us if you find any potential violation.
""")

colors = ["#0000FF","#FF0000","#00FF00","#FFFF00","#00FFFF","#FF00FF","#800080","#FFA500","#008000","#A52A2A","#FFC0CB","#00CED1","#8B008B","#FFD700","#7FFFD4","#FF4500","#2E8B57","#800000","#8A2BE2","#FF1493"]

class Chat:
    def __init__(self, model_path, conv_mode='default', model_base=None, load_8bit=False, load_4bit=False, device='cuda'):
        disable_torch_init()
        self.model, self.tokenizer, image_processor, video_transform, context_len = load_pretrained_model(model_path)
        self.image_processor = image_processor
        self.video_transform = video_transform
        self.conv_mode = conv_mode
        self.device = self.model.device
        print(self.model)

    def get_prompt(self, qs, state):
        state.append_message(state.roles[0], qs)
        state.append_message(state.roles[1], None)
        return state

    @torch.inference_mode()
    def generate(self, images_tensor: list, prompt: str, first_run: bool, state):
        tokenizer, model, image_processor, video_transform = self.tokenizer, self.model, self.image_processor, self.video_transform

        state = self.get_prompt(prompt, state)
        prompt = state.get_prompt()
        print('\n\n\n')
        print(prompt)
        input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors='pt').unsqueeze(0).cuda()
        image_tensor = None
        video_tensor = None
        sound_tensor = None
        for (tensor,modality) in zip(images_tensor[0],images_tensor[1]):
            if modality=='image':
                image_tensor=tensor
            if modality=='video':
                video_tensor=tensor
            if modality=='sound':
                sound_tensor=tensor
              
        stop_str = state.sep if state.sep_style != SeparatorStyle.TWO else state.sep2
        keywords = [stop_str]
        stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)
        # streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
        # print(input_ids, images_tensor[0][0].shape)
        with torch.inference_mode():
            output_ids = model.generate(
                input_ids,
                images=image_tensor,
                videos=video_tensor,
                sounds=sound_tensor,
                do_sample=True,
                temperature=0.2,
                max_new_tokens=1024,
                # streamer=streamer,
                use_cache=True,
                stopping_criteria=[stopping_criteria])

        input_token_len = input_ids.shape[1]
        n_diff_input_output = (input_ids != output_ids[:, :input_token_len]).sum().item()
        if n_diff_input_output > 0:
            print(f'[Warning] {n_diff_input_output} output_ids are not the same as the input_ids')
        outputs = tokenizer.batch_decode(output_ids[:, input_token_len:], skip_special_tokens=True)[0]
        outputs = outputs.strip()
        if outputs.endswith(stop_str):
            outputs = outputs[:-len(stop_str)]
        outputs = outputs.strip()

        print('response', outputs)
        return outputs, state
