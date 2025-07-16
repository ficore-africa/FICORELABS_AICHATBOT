import json
from translations import trans
from utils import logger

def process_dialogflow_request(request_data, lang='en'):
    """
    Process incoming Dialogflow webhook requests and return a JSON response.
    
    Args:
        request_data (str): JSON string from Dialogflow webhook
        lang (str): Language code ('en' or 'ha')
    
    Returns:
        str: JSON response for Dialogflow
    """
    try:
        data = json.loads(request_data)
        intent = data['queryResult']['intent']['displayName']
        
        if intent == 'How to get FCs':
            response_text = trans('chatbot_how_to_get_fcs', lang=lang, default='You can get FCs by clicking “Get More FCs” in your wallet section. FCs are added in-app and used for specific tools. No external bank needed.')
        elif intent == 'How to become an agent':
            response_text = trans('chatbot_how_to_become_agent', lang=lang, default='Visit the Agent section in the app and enter a valid Agent ID during sign-up. You’ll get onboarding materials after registration.')
        elif intent == 'Check my budget':
            response_text = trans('chatbot_check_budget', lang=lang, default='To check your budget, please go to the Budget section in the app.')
        elif intent == 'Tips on saving':
            response_text = trans('chatbot_saving_tips', lang=lang, default='Here are some tips on saving: 1. Track your expenses. 2. Set a budget. 3. Automate savings. 4. Reduce unnecessary expenses.')
        elif intent == 'How do I earn FCs':
            response_text = trans('chatbot_how_to_earn_fcs', lang=lang, default='You can earn FCs by completing certain tasks in the app, such as inviting friends or achieving financial goals.')
        else:
            response_text = trans('chatbot_fallback', lang=lang, default='I didn’t understand that. Please try one of the suggested questions.')
        
        response = {
            'fulfillmentText': response_text
        }
        return json.dumps(response)
    except Exception as e:
        logger.error(f'Error processing Dialogflow request: {str(e)}', exc_info=True)
        response_text = trans('chatbot_error', lang=lang, default='An error occurred. Please try again later.')
        return json.dumps({'fulfillmentText': response_text})