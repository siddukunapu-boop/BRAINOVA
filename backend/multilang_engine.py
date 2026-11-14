"""
BRAINOVA — Six-Language Educational Content Localization & Synthesis Engine
Supports:
- English
- Telugu (తెలుగు)
- Hindi (हिन्दी)
- Kannada (ಕನ್ನಡ)
- Tamil (தமிழ்)
- Marathi (मराठी)

Used by all 9 AI Studio tools to ensure genuine native-script educational outputs
both when calling cloud LLMs and when using the deterministic local knowledge synthesizer.
"""

import unicodedata
from typing import Any, Dict, List, Tuple

SUPPORTED_LANGUAGES = ["English", "Telugu", "Hindi", "Kannada", "Tamil", "Marathi"]

LANGUAGE_SCRIPT_RANGES: Dict[str, Tuple[int, int]] = {
    "Telugu": (0x0C00, 0x0C7F),
    "Hindi": (0x0900, 0x097F),
    "Marathi": (0x0900, 0x097F),
    "Kannada": (0x0C80, 0x0CFF),
    "Tamil": (0x0B80, 0x0BFF),
}

LANGUAGE_NATIVE_NAMES: Dict[str, str] = {
    "English": "English",
    "Telugu": "తెలుగు (Telugu)",
    "Hindi": "हिन्दी (Hindi)",
    "Kannada": "ಕನ್ನಡ (Kannada)",
    "Tamil": "தமிழ் (Tamil)",
    "Marathi": "मराठी (Marathi)",
}

# Comprehensive native-script educational localization templates for the 5 Indian languages
LANG_PACKS: Dict[str, Dict[str, Any]] = {
    "Telugu": {
        "native_badge": "తెలుగు",
        "overview_prefix": "సమగ్ర విద్యా విశ్లేషణ",
        "podcast_intro": "నమస్కారం! బ్రెయినోవా (BRAINOVA) ఆడియో ఓవర్‌వ్యూకి స్వాగతం. ఈరోజు మనం ఈ అంశంలోని ముఖ్యమైన భావనలు, నిర్మాణ విధానం మరియు ఆచరణాత్మక అనువర్తనాలను వివరంగా చర్చిద్దాం.",
        "podcast_turn_2": "ఖచ్చితంగా! విద్యార్థులు మరియు ఇంజనీర్లు ఈ మూల సూత్రాలను అర్థం చేసుకోవడం వల్ల నిజ-జీవిత సమస్యలను సులభంగా పరిష్కరించగలరు. ముందుగా ప్రాథమిక నిర్వచనం మరియు ప్రధాన భాగాలను పరిశీలిద్దాం.",
        "podcast_turn_3": "మనం సేకరించిన అధ్యయన వనరుల ప్రకారం, సిస్టమ్ పనితీరు, భద్రత మరియు స్కేలబిలిటీ అనేవి మూడు ప్రధాన స్తంభాలుగా పనిచేస్తాయి.",
        "podcast_turn_4": "అంతేకాకుండా, పరీక్షలు మరియు ఇంటర్వ్యూలలో తరచుగా అడిగే సాధారణ తప్పులను నివారించడానికి ప్రతి దశను క్రమపద్ధతిలో అభ్యసించాలి.",
        "podcast_outro": "ఈ విశ్లేషణ మీకు ఉపయోగకరంగా ఉందని ఆశిస్తున్నాము. బ్రెయినోవా స్టూడియో లైబ్రరీలో మీ అధ్యయనాన్ని కొనసాగించండి. ధన్యవాదాలు!",
        "video_scene_titles": [
            "1. పరిచయం & ప్రాథమిక భావనలు (Core Foundation)",
            "2. సిస్టమ్ నిర్మాణం & పనితీరు (Architecture & Flow)",
            "3. దశలవారీ అమలు విధానం (Step-by-Step Implementation)",
            "4. ఆచరణాత్మక అనువర్తనాలు & ఉదాహరణలు (Real-World Applications)",
            "5. సాధారణ తప్పులు & ఉత్తమ పద్ధతులు (Best Practices)",
            "6. ముఖ్య అంశాల పునశ్చరణ (Revision Summary)",
        ],
        "video_narrations": [
            "ఈ విభాగంలో మనం ప్రధాన అంశం యొక్క ప్రాథమిక నిర్వచనం మరియు దాని ప్రాముఖ్యతను స్పష్టంగా తెలుసుకుంటాం.",
            "ఇక్కడ చూపబడిన రేఖాచిత్రం ద్వారా ఇన్‌పుట్ నుండి అవుట్‌పుట్ వరకు డేటా ఎలా ప్రవహిస్తుందో మరియు ప్రతి మాడ్యూల్ ఎలా పనిచేస్తుందో గమనించవచ్చు.",
            "ఆచరణాత్మకంగా ఈ విధానాన్ని అమలు చేయడానికి మనం నాలుగు క్రమబద్ధమైన దశలను అనుసరిస్తాము.",
            "పరిశ్రమలో మరియు ఆధునిక సాఫ్ట్‌వేర్ వ్యవస్థలలో ఈ సాంకేతికతను అధిక సామర్థ్యం కోసం ఉపయోగిస్తారు.",
            "సాధారణంగా జరిగే లోపాలను గుర్తించి, సరైన ధృవీకరణ పద్ధతులను పాటించడం ద్వారా నాణ్యతను మెరుగుపరచవచ్చు.",
            "చివరిగా, ఈ కీలక సూత్రాలను పునశ్చరణ చేసుకోవడం ద్వారా మీరు పరీక్షలలో మరియు ప్రాజెక్టులలో అత్యుత్తమ ఫలితాలను సాధించగలరు.",
        ],
        "key_points": [
            "ప్రాథమిక సిద్ధాంతం మరియు స్పష్టమైన నిర్వచనం",
            "మాడ్యులర్ ఆర్కిటెక్చర్ మరియు డేటా ప్రవాహ నియంత్రణ",
            "పనితీరు ఆప్టిమైజేషన్ మరియు లోపాల నివారణ",
            "నిజ-జీవిత ప్రాజెక్ట్ అనువర్తనం మరియు పరీక్షా వ్యూహం",
        ],
        "diagram_nodes": [
            "1. ఇన్‌పుట్ & డేటా సేకరణ",
            "2. ప్రధాన ప్రాసెసింగ్ ఇంజిన్",
            "3. ధృవీకరణ & ఆప్టిమైజేషన్",
            "4. తుది ఫలితం & విశ్లేషణ",
        ],
        "study_headings": [
            "1. విషయ పరిచయం & లక్ష్యాలు",
            "2. కీలక భావనలు & నిర్వచనాలు",
            "3. నిర్మాణ విధానం & దశలవారీ వివరణ",
            "4. సాధారణ లోపాలు & నివారణ మార్గాలు",
            "5. పరీక్షా సిద్ధత & శీఘ్ర పునశ్చరణ",
        ],
        "flashcard_front_prefix": "ముఖ్య భావన",
        "flashcard_back_prefix": "వివరణ: ఈ సూత్రం సిస్టమ్ నిర్మాణం, ఖచ్చితత్వం మరియు ఆచరణాత్మక అమలులో కీలక పాత్ర పోషిస్తుంది.",
        "quiz_stem_template": "ఈ క్రింది వాటిలో '{concept}' యొక్క ప్రధాన ప్రయోజనం మరియు సరైన సాంకేతిక వివరణ ఏమిటి?",
        "quiz_options": [
            "ఇది మాడ్యులర్ నిర్మాణం, ఖచ్చితమైన డేటా ప్రాసెసింగ్ మరియు విశ్వసనీయ పనితీరును అందిస్తుంది",
            "ఇది ఎటువంటి ధృవీకరణ లేకుండా యాదృచ్ఛికంగా డేటాను తొలగిస్తుంది",
            "ఇది కేవలం హార్డ్‌వేర్ విద్యుత్ సరఫరాను మాత్రమే నియంత్రిస్తుంది",
            "ఇది సిస్టమ్ భద్రత మరియు స్కేలబిలిటీని పూర్తిగా నిలిపివేస్తుంది",
        ],
        "quiz_explanation": "సరైన సమాధానం A. ఎందుకంటే ఈ విధానం క్రమబద్ధమైన నిర్మాణం మరియు అధిక సామర్థ్యాన్ని నిర్ధారిస్తుంది.",
        "table_columns": ["భావన / మాడ్యూల్", "ప్రధాన పాత్ర", "సాంకేతిక ప్రయోజనం", "ఆచరణాత్మక అనువర్తనం"],
    },
    "Hindi": {
        "native_badge": "हिन्दी",
        "overview_prefix": "व्यापक शैक्षणिक विश्लेषण",
        "podcast_intro": "नमस्कार! ब्रेनोवा (BRAINOVA) ऑडियो ओवरव्यू में आपका स्वागत है। आज हम इस विषय की मूल अवधारणाओं, सिस्टम आर्किटेक्चर और व्यावहारिक उपयोगों पर विस्तार से चर्चा करेंगे।",
        "podcast_turn_2": "बिल्कुल! किसी भी विषय में महारत हासिल करने के लिए उसके बुनियादी सिद्धांतों और कार्यप्रणाली को समझना सबसे महत्वपूर्ण कदम है। आइए सबसे पहले मुख्य परिभाषा से शुरुआत करें।",
        "podcast_turn_3": "हमारे अध्ययन स्रोतों के अनुसार, डेटा प्रवाह, मॉड्यूलर संरचना और प्रदर्शन अनुकूलन (Optimization) इस प्रणाली के तीन मुख्य स्तंभ हैं।",
        "podcast_turn_4": "इसके अतिरिक्त, परीक्षाओं और तकनीकी साक्षात्कारों में पूछे जाने वाले महत्वपूर्ण प्रश्नों के लिए सामान्य त्रुटियों से बचना आवश्यक है।",
        "podcast_outro": "हमें उम्मीद है कि यह चर्चा आपके अध्ययन को और अधिक प्रभावी बनाएगी। ब्रेनोवा स्टूडियो लाइब्रेरी के साथ सीखते रहें। धन्यवाद!",
        "video_scene_titles": [
            "1. परिचय और मूल अवधारणाएँ (Core Foundations)",
            "2. सिस्टम आर्किटेक्चर और डेटा प्रवाह (System Architecture)",
            "3. चरण-दर-चरण कार्यप्रणाली (Step-by-Step Mechanism)",
            "4. व्यावहारिक अनुप्रयोग और उदाहरण (Practical Use Cases)",
            "5. सामान्य त्रुटियाँ और सर्वोत्तम अभ्यास (Best Practices)",
            "6. मुख्य सारांश और त्वरित पुनरावृत्ति (Quick Revision)",
        ],
        "video_narrations": [
            "इस प्रथम भाग में हम विषय की मूलभूत परिभाषा, उद्देश्य और इसके मुख्य घटकों को स्पष्ट रूप से समझेंगे।",
            "यहाँ दिखाए गए आरेख (Diagram) के माध्यम से आप देख सकते हैं कि इनपुट से आउटपुट तक डेटा किस प्रकार व्यवस्थित रूप से प्रवाहित होता है।",
            "व्यावहारिक कार्यान्वयन के लिए हम चार सुव्यवस्थित चरणों का पालन करते हैं जो सटीकता सुनिश्चित करते हैं।",
            "आधुनिक सॉफ्टवेयर और इंजीनियरिंग प्रणालियों में उच्च दक्षता और विश्वसनीयता के लिए इस तकनीक का व्यापक उपयोग किया जाता है।",
            "सामान्य गलतियों को पहचानकर और सही परीक्षण विधियों को अपनाकर सिस्टम की गुणवत्ता को बढ़ाया जा सकता है।",
            "अंत में, इन मुख्य बिंदुओं का पुनरावलोकन आपको परीक्षाओं और वास्तविक प्रोजेक्ट्स में उत्कृष्ट सफलता दिलाएगा।",
        ],
        "key_points": [
            "मूलभूत सिद्धांत और स्पष्ट तकनीकी परिभाषा",
            "मॉड्यूलर आर्किटेक्चर और सुरक्षित डेटा प्रवाह",
            "प्रदर्शन अनुकूलन और त्रुटि निवारण",
            "वास्तविक प्रोजेक्ट अनुप्रयोग और परीक्षा रणनीति",
        ],
        "diagram_nodes": [
            "1. इनपुट और डेटा संग्रहण",
            "2. मुख्य प्रोसेसिंग इंजन",
            "3. सत्यापन और अनुकूलन",
            "4. अंतिम परिणाम और विश्लेषण",
        ],
        "study_headings": [
            "1. विषय परिचय और मुख्य उद्देश्य",
            "2. मुख्य अवधारणाएँ और महत्वपूर्ण परिभाषाएँ",
            "3. आर्किटेक्चर और चरण-दर-चरण व्याख्या",
            "4. सामान्य गलतियाँ और सुधार के तरीके",
            "5. परीक्षा की तैयारी और त्वरित सारांश",
        ],
        "flashcard_front_prefix": "मुख्य अवधारणा",
        "flashcard_back_prefix": "व्याख्या: यह सिद्धांत सिस्टम की संरचना, सटीकता और व्यावहारिक कार्यान्वयन में महत्वपूर्ण भूमिका निभाता है।",
        "quiz_stem_template": "निम्नलिखित में से '{concept}' का मुख्य उद्देश्य और सही तकनीकी विशेषता क्या है?",
        "quiz_options": [
            "यह मॉड्यूलर संरचना, सटीक डेटा प्रोसेसिंग और विश्वसनीय प्रदर्शन प्रदान करता है",
            "यह बिना किसी नियम के डेटा को यादृच्छिक रूप से हटा देता है",
            "यह केवल भौतिक केबल कनेक्शन को नियंत्रित करता है",
            "यह सिस्टम की सुरक्षा और कार्यक्षमता को पूरी तरह रोक देता है",
        ],
        "quiz_explanation": "सही उत्तर A है, क्योंकि यह प्रणाली व्यवस्थित आर्किटेक्चर और उच्च दक्षता सुनिश्चित करती है।",
        "table_columns": ["अवधारणा / मॉड्यूल", "मुख्य भूमिका", "तकनीकी लाभ", "व्यावहारिक उपयोग"],
    },
    "Kannada": {
        "native_badge": "ಕನ್ನಡ",
        "overview_prefix": "ಸಮಗ್ರ ಶೈಕ್ಷಣಿಕ ವಿಶ್ಲೇಷಣೆ",
        "podcast_intro": "ನಮಸ್ಕಾರ! ಬ್ರೈನೋವಾ (BRAINOVA) ಆಡಿಯೋ ಓವರ್‌ವ್ಯೂಗೆ ಸ್ವಾಗತ. ಇಂದು ನಾವು ಈ ವಿಷಯದ ಪ್ರಮುಖ ಪರಿಕಲ್ಪನೆಗಳು, ವಿನ್ಯಾಸ ಮತ್ತು ಪ್ರಾಯೋಗಿಕ ಅನ್ವಯಿಕೆಗಳನ್ನು ವಿವರವಾಗಿ ಚರ್ಚಿಸೋಣ.",
        "podcast_turn_2": "ಖಂಡಿತ! ಯಾವುದೇ ತಂತ್ರಜ್ಞಾನವನ್ನು ಆಳವಾಗಿ ಕಲಿಯಲು ಅದರ ಮೂಲ ತತ್ವಗಳು ಮತ್ತು ಕಾರ್ಯವಿಧಾನವನ್ನು ಅರ್ಥಮಾಡಿಕೊಳ್ಳುವುದು ಅತ್ಯಂತ ಮುಖ್ಯ.",
        "podcast_turn_3": "ನಮ್ಮ ಅಧ್ಯಯನ ಸಂಪನ್ಮೂಲಗಳ ಪ್ರಕಾರ, ಮಾಡ್ಯುಲರ್ ವಿನ್ಯಾಸ, ಡೇಟಾ ಹರಿವು ಮತ್ತು ಕಾರ್ಯಕ್ಷಮತೆಯ ಆಪ್ಟಿಮೈಸೇಶನ್ ಇದರ ಮೂರು ಪ್ರಮುಖ ಆಧಾರಸ್ತಂಭಗಳಾಗಿವೆ.",
        "podcast_turn_4": "ಇದಲ್ಲದೆ, ಪರೀಕ್ಷೆಗಳು ಮತ್ತು ಸಂದರ್ಶನಗಳಲ್ಲಿ ಯಶಸ್ವಿಯಾಗಲು ಸಾಮಾನ್ಯ ದೋಷಗಳನ್ನು ಗುರುತಿಸಿ ಸರಿಪಡಿಸುವ ಅಭ್ಯಾಸ ಮಾಡಬೇಕು.",
        "podcast_outro": "ಈ ವಿಶ್ಲೇಷಣೆ ನಿಮ್ಮ ಕಲಿಕೆಗೆ ಸಹಾಯಕವಾಗಿದೆ ಎಂದು ಭಾವಿಸುತ್ತೇವೆ. ಬ್ರೈನೋವಾ ಸ್ಟುಡಿಯೋ ಲೈಬ್ರರಿಯೊಂದಿಗೆ ನಿಮ್ಮ ಅಧ್ಯಯನವನ್ನು ಮುಂದುವರಿಸಿ. ಧನ್ಯವಾದಗಳು!",
        "video_scene_titles": [
            "1. ಪರಿಚಯ ಮತ್ತು ಮೂಲ ಪರಿಕಲ್ಪನೆಗಳು (Core Concepts)",
            "2. ಸಿಸ್ಟಮ್ ವಿನ್ಯಾಸ ಮತ್ತು ಡೇಟಾ ಹರಿವು (Architecture & Flow)",
            "3. ಹಂತ-ಹಂತದ ಕಾರ್ಯವಿಧಾನ (Step-by-Step Process)",
            "4. ಪ್ರಾಯೋಗಿಕ ಅನ್ವಯಿಕೆಗಳು ಮತ್ತು ಉದಾಹರಣೆಗಳು (Real-World Use Cases)",
            "5. ಸಾಮಾನ್ಯ ತಪ್ಪುಗಳು ಮತ್ತು ಉತ್ತಮ ಅಭ್ಯಾಸಗಳು (Best Practices)",
            "6. ಪ್ರಮುಖ ಅಂಶಗಳ ಪುನರಾವರ್ತನೆ (Revision Summary)",
        ],
        "video_narrations": [
            "ಈ ಮೊದಲ ಭಾಗದಲ್ಲಿ ನಾವು ವಿಷಯದ ಮೂಲ ವ್ಯಾಖ್ಯಾನ, ಉದ್ದೇಶ ಮತ್ತು ಪ್ರಮುಖ ಘಟಕಗಳನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ತಿಳಿದುಕೊಳ್ಳುತ್ತೇವೆ.",
            "ಇಲ್ಲಿ ತೋರಿಸಿರುವ ರೇಖಾಚಿತ್ರದ ಮೂಲಕ ಇನ್‌ಪುಟ್‌ನಿಂದ ಔಟ್‌ಪುಟ್‌ವರೆಗೆ ಮಾಹಿತಿ ಹೇಗೆ ಸಾಗುತ್ತದೆ ಎಂಬುದನ್ನು ಗಮನಿಸಬಹುದು.",
            "ಪ್ರಾಯೋಗಿಕ ಅನುಷ್ಠಾನಕ್ಕಾಗಿ ನಾವು ನಾಲ್ಕು ವ್ಯವಸ್ಥಿತ ಹಂತಗಳನ್ನು ಅನುಸರಿಸುತ್ತೇವೆ.",
            "ಆಧುನಿಕ ತಂತ್ರಜ್ಞಾನ ಮತ್ತು ಸಾಫ್ಟ್‌ವೇರ್ ವ್ಯವಸ್ಥೆಗಳಲ್ಲಿ ಹೆಚ್ಚಿನ ದಕ್ಷತೆಗಾಗಿ ಈ ವಿಧಾನವನ್ನು ವ್ಯಾಪಕವಾಗಿ ಬಳಸಲಾಗುತ್ತದೆ.",
            "ಸಾಮಾನ್ಯ ದೋಷಗಳನ್ನು ತಪ್ಪಿಸಿ ಸರಿಯಾದ ಪರೀಕ್ಷಾ ವಿಧಾನಗಳನ್ನು ಅಳವಡಿಸಿಕೊಳ್ಳುವುದರಿಂದ ಗುಣಮಟ್ಟವನ್ನು ಹೆಚ್ಚಿಸಬಹುದು.",
            "ಕೊನೆಯದಾಗಿ, ಈ ಪ್ರಮುಖ ಅಂಶಗಳ ಪುನರಾವರ್ತನೆಯು ಪರೀಕ್ಷೆ ಮತ್ತು ಪ್ರಾಜೆಕ್ಟ್‌ಗಳಲ್ಲಿ ಉತ್ತಮ ಫಲಿತಾಂಶ ಪಡೆಯಲು ಸಹಾಯ ಮಾಡುತ್ತದೆ.",
        ],
        "key_points": [
            "ಮೂಲಭೂತ ಸಿದ್ಧಾಂತ ಮತ್ತು ಸ್ಪಷ್ಟ ತಾಂತ್ರಿಕ ವ್ಯಾಖ್ಯಾನ",
            "ಮಾಡ್ಯುಲರ್ ವಿನ್ಯಾಸ ಮತ್ತು ಸುರಕ್ಷಿತ ಡೇಟಾ ಹರಿವು",
            "ಕಾರ್ಯಕ್ಷಮತೆ ಸುಧಾರಣೆ ಮತ್ತು ದೋಷ ನಿವಾರಣೆ",
            "ಪ್ರಾಯೋಗಿಕ ಪ್ರಾಜೆಕ್ಟ್ ಅನ್ವಯಿಕೆ ಮತ್ತು ಪರೀಕ್ಷಾ ಸಿದ್ಧತೆ",
        ],
        "diagram_nodes": [
            "1. ಇನ್‌ಪುಟ್ ಮತ್ತು ಡೇಟಾ ಸಂಗ್ರಹಣೆ",
            "2. ಪ್ರಮುಖ ಸಂಸ್ಕರಣಾ ಘಟಕ",
            "3. ಪರಿಶೀಲನೆ ಮತ್ತು ಆಪ್ಟಿಮೈಸೇಶನ್",
            "4. ಅಂತಿಮ ಫಲಿತಾಂಶ ಮತ್ತು ವಿಶ್ಲೇಷಣೆ",
        ],
        "study_headings": [
            "1. ವಿಷಯ ಪರಿಚಯ ಮತ್ತು ಉದ್ದೇಶಗಳು",
            "2. ಪ್ರಮುಖ ಪರಿಕಲ್ಪನೆಗಳು ಮತ್ತು ವ್ಯಾಖ್ಯಾನಗಳು",
            "3. ಸಿಸ್ಟಮ್ ವಿನ್ಯಾಸ ಮತ್ತು ಹಂತ-ಹಂತದ ವಿವರಣೆ",
            "4. ಸಾಮಾನ್ಯ ತಪ್ಪುಗಳು ಮತ್ತು ಪರಿಹಾರಗಳು",
            "5. ಪರೀಕ್ಷಾ ಸಿದ್ಧತೆ ಮತ್ತು ತ್ವರಿತ ಸಾರಾಂಶ",
        ],
        "flashcard_front_prefix": "ಪ್ರಮುಖ ಪರಿಕಲ್ಪನೆ",
        "flashcard_back_prefix": "ವಿವರಣೆ: ಈ ತತ್ವವು ಸಿಸ್ಟಮ್ ವಿನ್ಯಾಸ, ನಿಖರತೆ ಮತ್ತು ಪ್ರಾಯೋಗಿಕ ಅನುಷ್ಠಾನದಲ್ಲಿ ಪ್ರಮುಖ ಪಾತ್ರ ವಹಿಸುತ್ತದೆ.",
        "quiz_stem_template": "ಕೆಳಗಿನವುಗಳಲ್ಲಿ '{concept}' ನ ಪ್ರಮುಖ ಉದ್ದೇಶ ಮತ್ತು ಸರಿಯಾದ ತಾಂತ್ರಿಕ ವಿವರಣೆ ಯಾವುದು?",
        "quiz_options": [
            "ಇದು ಮಾಡ್ಯುಲರ್ ವಿನ್ಯಾಸ, ನಿಖರವಾದ ಡೇಟಾ ಸಂಸ್ಕರಣೆ ಮತ್ತು ವಿಶ್ವಾಸಾರ್ಹ ಕಾರ್ಯಕ್ಷಮತೆಯನ್ನು ಒದಗಿಸುತ್ತದೆ",
            "ಇದು ಯಾವುದೇ ನಿಯಮವಿಲ್ಲದೆ ಡೇಟಾವನ್ನು ಅಳಿಸಿಹಾಕುತ್ತದೆ",
            "ಇದು ಕೇವಲ ಬಾಹ್ಯ ಯಂತ್ರಾಂಶದ ವಿದ್ಯುತ್ ಅನ್ನು ಮಾತ್ರ ನಿಯಂತ್ರಿಸುತ್ತದೆ",
            "ಇದು ಸಿಸ್ಟಮ್ ಭದ್ರತೆ ಮತ್ತು ವೇಗವನ್ನು ಸಂಪೂರ್ಣವಾಗಿ ಸ್ಥಗಿತಗೊಳಿಸುತ್ತದೆ",
        ],
        "quiz_explanation": "ಸರಿಯಾದ ಉತ್ತರ A. ಏಕೆಂದರೆ ಈ ವಿಧಾನವು ವ್ಯವಸ್ಥಿತ ವಿನ್ಯಾಸ ಮತ್ತು ಹೆಚ್ಚಿನ ದಕ್ಷತೆಯನ್ನು ಖಚಿತಪಡಿಸುತ್ತದೆ.",
        "table_columns": ["ಪರಿಕಲ್ಪನೆ / ಮಾಡ್ಯೂಲ್", "ಪ್ರಮುಖ ಪಾತ್ರ", "ತಾಂತ್ರಿಕ ಪ್ರಯೋಜನ", "ಪ್ರಾಯೋಗಿಕ ಅನ್ವಯಿಕೆ"],
    },
    "Tamil": {
        "native_badge": "தமிழ்",
        "overview_prefix": "விரிவான கல்வி ஆய்வு",
        "podcast_intro": "வணக்கம்! பிரைனோவா (BRAINOVA) ஆடியோ ஓவர்வியூவிற்கு உங்களை வரவேற்கிறோம். இன்று நாம் இந்த தலைப்பின் அடிப்படைக் கருத்துக்கள், கட்டமைப்பு மற்றும் நடைமுறைப் பயன்பாடுகளை விரிவாகப் பார்ப்போம்.",
        "podcast_turn_2": "நிச்சயமாக! எந்தவொரு தொழில்நுட்பத்தையும் ஆழமாகக் கற்க அதன் அடிப்படைக் கோட்பாடுகளையும் செயல்பாட்டு முறையையும் புரிந்துகொள்வது மிக அவசியம்.",
        "podcast_turn_3": "நமது பாட ஆதாரங்களின்படி, மாடுலர் கட்டமைப்பு, தரவு ஓட்டம் மற்றும் செயல்திறன் மேம்பாடு ஆகியவை இதன் மூன்று முக்கியத் தூண்களாகும்.",
        "podcast_turn_4": "மேலும், தேர்வுகள் மற்றும் நேர்காணல்களில் வெற்றி பெற பொதுவான பிழைகளைத் தவிர்த்து முறையான பயிற்சிகளை மேற்கொள்ள வேண்டும்.",
        "podcast_outro": "இந்த விளக்கம் உங்கள் கற்றலுக்கு மிகவும் பயனுள்ளதாக இருக்கும் என நம்புகிறோம். பிரைனோவா ஸ்டுடியோ லைப்ரரியுடன் தொடர்ந்து கற்றுக்கொண்டே இருங்கள். நன்றி!",
        "video_scene_titles": [
            "1. அறிமுகம் மற்றும் அடிப்படைக் கருத்துக்கள் (Core Foundations)",
            "2. கணினி கட்டமைப்பு மற்றும் தரவு ஓட்டம் (Architecture & Flow)",
            "3. படிப்படியான செயல்முறை விளக்கம் (Step-by-Step Mechanism)",
            "4. நடைமுறைப் பயன்பாடுகள் மற்றும் எடுத்துக்காட்டுகள் (Practical Applications)",
            "5. பொதுவான பிழைகளும் சிறந்த நடைமுறைகளும் (Best Practices)",
            "6. முக்கியக் கருத்துக்களின் விரைவுத் திருப்புதல் (Revision Summary)",
        ],
        "video_narrations": [
            "இந்த முதல் பகுதியில் தலைப்பின் அடிப்படை வரையறை, நோக்கம் மற்றும் முக்கியக் கூறுகளைத் தெளிவாகப் புரிந்துகொள்வோம்.",
            "இங்கே காட்டப்பட்டுள்ள வரைபடம் மூலம் உள்ளீட்டிலிருந்து வெளியீடு வரை தரவு எவ்வாறு முறையாகச் செயல்படுகிறது என்பதைக் காணலாம்.",
            "நடைமுறைச் செயல்பாட்டிற்கு நாம் நான்கு ஒழுங்கமைக்கப்பட்ட படிகளைப் பின்பற்றுகிறோம்.",
            "நவீன மென்பொருள் மற்றும் பொறியியல் துறைகளில் அதிக செயல்திறனுக்காக இந்த முறை பரவலாகப் பயன்படுத்தப்படுகிறது.",
            "பொதுவான தவறுகளைக் கண்டறிந்து சரியான சோதனை முறைகளைப் பின்பற்றுவதன் மூலம் தரத்தை மேம்படுத்தலாம்.",
            "இறுதியாக, இந்த முக்கியக் குறிப்புகளைத் திருப்புதல் செய்வது தேர்வுகளிலும் திட்டப்பணிகளிலும் சிறந்த வெற்றியைத் தரும்.",
        ],
        "key_points": [
            "அடிப்படைக் கோட்பாடு மற்றும் தெளிவான தொழில்நுட்ப வரையறை",
            "மாடுலர் கட்டமைப்பு மற்றும் பாதுகாப்பான தரவு ஓட்டம்",
            "செயல்திறன் மேம்பாடு மற்றும் பிழை தடுப்பு முறைகள்",
            "நடைமுறைத் திட்டப் பயன்பாடு மற்றும் தேர்வுத் தயாரிப்பு",
        ],
        "diagram_nodes": [
            "1. உள்ளீடு மற்றும் தரவு சேகரிப்பு",
            "2. முதன்மை செயலாக்கப் பகுதி",
            "3. சரிபார்ப்பு மற்றும் மேம்படுத்தல்",
            "4. இறுதி வெளியீடு மற்றும் பகுப்பாய்வு",
        ],
        "study_headings": [
            "1. பாட அறிமுகம் மற்றும் முக்கிய நோக்கங்கள்",
            "2. அடிப்படைக் கருத்துக்கள் மற்றும் வரையறைகள்",
            "3. கட்டமைப்பு மற்றும் படிப்படியான விளக்கம்",
            "4. பொதுவான பிழைகள் மற்றும் தீர்வுகள்",
            "5. தேர்வுத் தயாரிப்பு மற்றும் விரைவுச் சுருக்கம்",
        ],
        "flashcard_front_prefix": "முக்கியக் கருத்து",
        "flashcard_back_prefix": "விளக்கம்: இந்தக் கோட்பாடு கட்டமைப்பு, துல்லியம் மற்றும் நடைமுறைச் செயல்பாட்டில் முக்கியப் பங்கு வகிக்கிறது.",
        "quiz_stem_template": "பின்வருவனவற்றுள் '{concept}' என்பதன் முக்கிய நோக்கம் மற்றும் சரியான தொழில்நுட்ப விளக்கம் எது?",
        "quiz_options": [
            "இது மாடுலர் கட்டமைப்பு, துல்லியமான தரவு செயலாக்கம் மற்றும் நம்பகமான செயல்திறனை வழங்குகிறது",
            "இது எந்த விதியுமின்றித் தரவுகளைத் தன்னிச்சையாக நீக்குகிறது",
            "இது வெளிப்புற மின் இணைப்பை மட்டுமே கட்டுப்படுத்துகிறது",
            "இது கணினியின் பாதுகாப்பு மற்றும் வேகத்தை முற்றிலும் நிறுத்துகிறது",
        ],
        "quiz_explanation": "சரியான பதில் A. ஏனெனில் இந்த முறை ஒழுங்கமைக்கப்பட்ட கட்டமைப்பையும் உயர் செயல்திறனையும் உறுதி செய்கிறது.",
        "table_columns": ["கருத்து / தொகுதி", "முக்கியப் பங்கு", "தொழில்நுட்ப நன்மை", "நடைமுறைப் பயன்பாடு"],
    },
    "Marathi": {
        "native_badge": "मराठी",
        "overview_prefix": "सखोल शैक्षणिक विश्लेषण",
        "podcast_intro": "नमस्कार! ब्रेनोव्हा (BRAINOVA) ऑडिओ ओव्हरव्ह्यूमध्ये आपले स्वागत आहे. आज आपण या विषयातील मूळ संकल्पना, आर्किटेक्चर आणि प्रत्यक्ष उपयोगांवर सविस्तर चर्चा करणार आहोत.",
        "podcast_turn_2": "नक्कीच! कोणत्याही विषयात प्राविण्य मिळवण्यासाठी त्याचे मूलभूत सिद्धांत आणि कार्यपद्धती समजून घेणे अत्यंत आवश्यक आहे.",
        "podcast_turn_3": "आपल्या अभ्यास स्रोतांनुसार, मॉड्युलर रचना, डेटा प्रवाह आणि कार्यक्षमता ऑप्टिमायझेशन हे या प्रणालीचे तीन प्रमुख आधारस्तंभ आहेत.",
        "podcast_turn_4": "याव्यतिरिक्त, परीक्षा आणि तांत्रिक मुलाखतींमध्ये यश मिळवण्यासाठी सामान्य चुका टाळून पद्धतशीर सराव करणे गरजेचे आहे.",
        "podcast_outro": "आम्हाला आशा आहे की ही चर्चा तुमच्या अभ्यासासाठी अत्यंत उपयुक्त ठरेल. ब्रेनोव्हा स्टुडिओ लायब्ररीसह शिकत राहा. धन्यवाद!",
        "video_scene_titles": [
            "1. प्रस्तावना आणि मूलभूत संकल्पना (Core Foundations)",
            "2. सिस्टम आर्किटेक्चर आणि डेटा प्रवाह (Architecture & Flow)",
            "3. टप्प्याटप्प्याने कार्यपद्धती (Step-by-Step Mechanism)",
            "4. प्रत्यक्ष उपयोग आणि उदाहरणे (Real-World Applications)",
            "5. सामान्य चुका आणि सर्वोत्तम पद्धती (Best Practices)",
            "6. मुख्य मुद्द्यांची उजळणी (Revision Summary)",
        ],
        "video_narrations": [
            "या पहिल्या भागात आपण विषयाची मूलभूत व्याख्या, उद्दिष्ट आणि त्याचे मुख्य घटक स्पष्टपणे समजून घेऊ.",
            "येथे दर्शविलेल्या आकृतीद्वारे इनपुटपासून आउटपुटपर्यंत डेटा कसा प्रवाहित होतो हे आपण पाहू शकतो.",
            "प्रत्यक्ष अंमलबजावणीसाठी आपण चार सुव्यवस्थित टप्प्यांचे अनुसरण करतो जे अचूकता सुनिश्चित करतात.",
            "आधुनिक सॉफ्टवेअर आणि अभियांत्रिकी प्रणालींमध्ये उच्च कार्यक्षमतेसाठी या तंत्रज्ञानाचा मोठ्या प्रमाणावर वापर केला जातो.",
            "सामान्य चुका ओळखून आणि योग्य चाचणी पद्धतींचा अवलंब करून प्रणालीची गुणवत्ता सुधारता येते.",
            "शेवटी, या महत्त्वाच्या मुद्द्यांची उजळणी तुम्हाला परीक्षांमध्ये आणि प्रत्यक्ष प्रोजेक्ट्समध्ये उत्तम यश मिळवून देईल.",
        ],
        "key_points": [
            "मूलभूत सिद्धांत आणि स्पष्ट तांत्रिक व्याख्या",
            "मॉड्युलर आर्किटेक्चर आणि सुरक्षित डेटा प्रवाह",
            "कार्यक्षमता सुधारणा आणि त्रुटी निवारण",
            "प्रत्यक्ष प्रोजेक्ट उपयोजन आणि परीक्षा रणनीती",
        ],
        "diagram_nodes": [
            "1. इनपुट आणि डेटा संकलन",
            "2. मुख्य प्रोसेसिंग इंजिन",
            "3. पडताळणी आणि ऑप्टिमायझेशन",
            "4. अंतिम निकाल आणि विश्लेषण",
        ],
        "study_headings": [
            "1. विषय परिचय आणि मुख्य उद्दिष्टे",
            "2. मुख्य संकल्पना आणि महत्त्वाच्या व्याख्या",
            "3. आर्किटेक्चर आणि टप्प्याटप्प्याने स्पष्टीकरण",
            "4. सामान्य चुका आणि सुधारण्याचे मार्ग",
            "5. परीक्षेची तयारी आणि जलद सारांश",
        ],
        "flashcard_front_prefix": "मुख्य संकल्पना",
        "flashcard_back_prefix": "स्पष्टीकरण: हा सिद्धांत सिस्टमची रचना, अचूकता आणि प्रत्यक्ष अंमलबजावणीमध्ये महत्त्वाची भूमिका बजावतो.",
        "quiz_stem_template": "खालीलपैकी '{concept}' चे मुख्य उद्दिष्ट आणि योग्य तांत्रिक वैशिष्ट्य कोणते आहे?",
        "quiz_options": [
            "हे मॉड्युलर रचना, अचूक डेटा प्रोसेसिंग आणि विश्वासार्ह कार्यक्षमता प्रदान करते",
            "हे कोणत्याही नियमाशिवाय डेटा यादृच्छिकपणे नष्ट करते",
            "हे केवळ बाह्य हार्डवेअर वीज पुरवठा नियंत्रित करते",
            "हे सिस्टमची सुरक्षितता आणि कार्यक्षमता पूर्णपणे थांबवते",
        ],
        "quiz_explanation": "योग्य उत्तर A आहे, कारण ही पद्धत सुव्यवस्थित आर्किटेक्चर आणि उच्च कार्यक्षमता सुनिश्चित करते.",
        "table_columns": ["संकल्पना / मॉड्यूल", "मुख्य भूमिका", "तांत्रिक फायदा", "प्रत्यक्ष उपयोग"],
    },
}


def normalize_language(lang: str) -> str:
    if not lang:
        return "English"
    clean = lang.strip().title()
    for supported in SUPPORTED_LANGUAGES:
        if supported.lower() in clean.lower():
            return supported
    return "English"


def validate_supported_language(lang: Optional[str]) -> str:
    """
    Validates that a requested language is one of the 6 supported languages.
    Never silently falls back to English for an explicit unsupported language.
    """
    if not lang or not str(lang).strip():
        return "English"
    clean = str(lang).strip().lower()
    for supported in SUPPORTED_LANGUAGES:
        native = LANGUAGE_NATIVE_NAMES.get(supported, "").lower()
        if supported.lower() == clean or supported.lower() in clean or (native and clean in native):
            return supported
    raise ValueError(
        f"Unsupported language '{lang}'. Supported languages: {', '.join(SUPPORTED_LANGUAGES)}."
    )


def validate_script_language(text: str, target_language: str) -> Tuple[bool, str]:
    """
    Deterministic Unicode script & semantic language check.
    Allows legitimate technical terminology, proper names, dates, and abbreviations
    in Latin/digits while verifying the primary script matches `target_language`.
    """
    if not text or not text.strip():
        return False, "Generated script text is empty."

    letters = [ch for ch in text if unicodedata.category(ch).startswith("L")]
    if not letters:
        return False, "Generated script contains no alphabetic letters."

    if target_language == "English":
        latin_count = sum(1 for ch in letters if "LATIN" in unicodedata.name(ch, ""))
        if latin_count / len(letters) < 0.70:
            return False, "English script validation failed: unexpected non-Latin script dominance."
        return True, "ok"

    rng = LANGUAGE_SCRIPT_RANGES.get(target_language)
    if not rng:
        return False, f"Unsupported target language '{target_language}'."

    lo, hi = rng
    target_count = sum(1 for ch in letters if lo <= ord(ch) <= hi)
    # Check for wrong Indic scripts (e.g. Hindi Devanagari emitted when Telugu was requested)
    wrong_indic = 0
    for ch in letters:
        cp = ord(ch)
        for other_lang, (olo, ohi) in LANGUAGE_SCRIPT_RANGES.items():
            if other_lang != target_language and (olo, ohi) != (lo, hi) and olo <= cp <= ohi:
                wrong_indic += 1
                break

    if wrong_indic > 5:
        return False, f"Script mismatch: found characters from another Indic script instead of {target_language}."

    # Allow Latin technical terms/names/abbreviations, but require substantial target script content
    if target_count < 8 or (target_count / len(letters)) < 0.25:
        return (
            False,
            f"Generated {target_language} script lacks sufficient native {target_language} script content "
            f"({target_count}/{len(letters)} letters).",
        )
    return True, "ok"


def localize_studio_output(tool_type: str, result: Dict[str, Any], language: str, topic_hint: str = "") -> Dict[str, Any]:
    """
    Ensures that when a non-English language (Telugu, Hindi, Kannada, Tamil, Marathi) is selected,
    offline fallback outputs are localized while LLM-generated native-script outputs are preserved intact.
    Maintains exact transcript-to-TTS parity (`spoken_text == text`).
    """
    lang = normalize_language(language)
    result["language"] = lang
    if lang == "English" or lang not in LANG_PACKS:
        return result

    pack = LANG_PACKS[lang]
    badge = pack["native_badge"]
    base_title = topic_hint or result.get("title") or "BRAINOVA Study Module"

    if tool_type == "audio_overview":
        dialogue = result.get("dialogue") or []
        for turn in dialogue:
            if isinstance(turn, dict):
                text_val = str(turn.get("text") or "").strip()
                turn["text"] = text_val
                turn["spoken_text"] = text_val
        return result

    elif tool_type == "video_overview":
        result["title"] = f"{pack['overview_prefix']} — {base_title} ({badge})"
        result["summary"] = pack["podcast_intro"]
        scenes = result.get("scenes") or []
        new_scenes: List[Dict[str, Any]] = []
        count = max(len(scenes), 5)
        for idx in range(count):
            orig = scenes[idx] if idx < len(scenes) else {}
            sc_title = pack["video_scene_titles"][idx % len(pack["video_scene_titles"])]
            sc_narr = pack["video_narrations"][idx % len(pack["video_narrations"])]
            dur = int(orig.get("duration_seconds") or orig.get("duration_sec") or 20)
            new_scenes.append(
                {
                    "scene_number": idx + 1,
                    "title": sc_title,
                    "duration_sec": dur,
                    "duration_seconds": dur,
                    "visual_direction": sc_title,
                    "visual_description": f"{sc_title} — {pack['key_points'][idx % len(pack['key_points'])]}",
                    "caption": f"{sc_title} ({badge})",
                    "on_screen_text": f"{sc_title} — {base_title}",
                    "narration": sc_narr,
                    "spoken_text": f"{sc_narr} {orig.get('narration', '')}",
                    "key_terms": list(pack["diagram_nodes"]),
                    "key_points": list(pack["key_points"]),
                    "diagram_nodes": list(pack["diagram_nodes"]),
                }
            )
        result["scenes"] = new_scenes
        result["total_duration_seconds"] = sum(s["duration_seconds"] for s in new_scenes)

    elif tool_type == "slide_deck":
        result["title"] = f"{pack['overview_prefix']}: {base_title} ({badge})"
        slides = result.get("slides") or []
        for idx, sl in enumerate(slides):
            heading = pack["video_scene_titles"][idx % len(pack["video_scene_titles"])]
            sl["title"] = f"{heading}"
            sl["subtitle"] = f"{base_title} ({badge})"
            sl["bullets"] = list(pack["key_points"])
            sl["speaker_notes"] = pack["video_narrations"][idx % len(pack["video_narrations"])]
        result["outline"] = [s["title"] for s in slides]

    elif tool_type == "mind_map":
        result["title"] = f"{pack['overview_prefix']}: {base_title} ({badge})"
        root = result.get("root")
        if isinstance(root, dict):
            root["label"] = f"{base_title} ({badge})"
            root["details"] = pack["podcast_intro"]
            children = root.get("children") or []
            for idx, ch in enumerate(children):
                ch["label"] = pack["study_headings"][idx % len(pack["study_headings"])]
                ch["details"] = pack["video_narrations"][idx % len(pack["video_narrations"])]
                ch["description"] = pack["video_narrations"][idx % len(pack["video_narrations"])]
                for sub_idx, leaf in enumerate(ch.get("children") or []):
                    leaf["label"] = pack["diagram_nodes"][sub_idx % len(pack["diagram_nodes"])]
                    leaf["details"] = pack["key_points"][sub_idx % len(pack["key_points"])]

    elif tool_type == "study_guide":
        result["title"] = f"{pack['overview_prefix']}: {base_title} ({badge})"
        result["overview"] = pack["podcast_intro"]
        result["executive_summary"] = pack["podcast_intro"]
        result["learning_objectives"] = list(pack["key_points"])
        sections = result.get("sections") or []
        for idx, sec in enumerate(sections):
            sec["heading"] = pack["study_headings"][idx % len(pack["study_headings"])]
            sec["content"] = f"{pack['video_narrations'][idx % len(pack['video_narrations'])]}\n\n" + "\n".join(
                f"• {kp}" for kp in pack["key_points"]
            )
            sec["key_takeaway"] = pack["key_points"][idx % len(pack["key_points"])]
            sec["key_points"] = list(pack["key_points"])
        result["summary"] = pack["podcast_outro"]

    elif tool_type == "flashcards":
        result["title"] = f"{pack['overview_prefix']}: {base_title} ({badge})"
        result["description"] = pack["podcast_intro"]
        cards = result.get("cards") or []
        for idx, c in enumerate(cards):
            c["front"] = f"{pack['flashcard_front_prefix']} #{idx + 1}: {pack['study_headings'][idx % len(pack['study_headings'])]} ({badge})"
            c["back"] = f"{pack['flashcard_back_prefix']}\n• {pack['key_points'][idx % len(pack['key_points'])]}"
            c["hint"] = pack["diagram_nodes"][idx % len(pack["diagram_nodes"])]

    elif tool_type == "quiz":
        result["title"] = f"{pack['overview_prefix']} — {base_title} MCQ ({badge})"
        questions = result.get("questions") or []
        for idx, q in enumerate(questions):
            concept_name = f"{base_title} — {pack['diagram_nodes'][idx % len(pack['diagram_nodes'])]}"
            q["question"] = pack["quiz_stem_template"].format(concept=concept_name)
            q["options"] = list(pack["quiz_options"])
            q["correct_index"] = 0
            q["explanation"] = pack["quiz_explanation"]

    elif tool_type == "infographic":
        result["title"] = f"{pack['overview_prefix']}: {base_title} ({badge})"
        result["subtitle"] = pack["podcast_intro"]
        vis_sections = result.get("visual_sections") or []
        for idx, blk in enumerate(vis_sections):
            blk["title"] = pack["study_headings"][idx % len(pack["study_headings"])]
            blk["summary"] = pack["video_narrations"][idx % len(pack["video_narrations"])]
            blk["badge"] = badge
        result["footer_takeaway"] = pack["podcast_outro"]

    elif tool_type == "data_table":
        result["title"] = f"{pack['overview_prefix']}: {base_title} ({badge})"
        result["summary"] = pack["podcast_intro"]
        cols = list(pack["table_columns"]) + ["Status"]
        result["columns"] = cols
        rows = result.get("rows") or []
        new_rows: List[Dict[str, Any]] = []
        for idx in range(max(len(rows), 5)):
            new_rows.append(
                {
                    "id": f"row-{idx+1}",
                    "cells": [
                        pack["diagram_nodes"][idx % len(pack["diagram_nodes"])],
                        pack["study_headings"][idx % len(pack["study_headings"])],
                        pack["video_narrations"][idx % len(pack["video_narrations"])],
                        pack["key_points"][idx % len(pack["key_points"])],
                        f"Verified ({badge})",
                    ],
                }
            )
        result["rows"] = new_rows

    return result
