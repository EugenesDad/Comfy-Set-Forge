    let config = null;
    let library = null;
    let modelLists = {};
    let dbCurrentKey = "";
    let dbCurrentGroupKey = "";
    let dbEditorSection = "global_positive";
    let dbEditorKey = "";
    let dbDirty = false;
    let dbDragJustEnded = false;
    let dbDragContext = null;
    let configSaveTimer = null;
    let librarySaveTimer = null;
    let singleSourceImageData = "";
    let singleSourceFileName = "";
    let lastSinglePreviewName = "";

    const $ = (id) => document.getElementById(id);

        const UI_TRANSLATIONS = {
      "zh-Hant": {
        ": Appended directly to the image prompt. When multiple objects are selected, all selected object prompts are inserted into every image; they do not increase the loop multiplier like characters, outfits, and actions.": "：直接追加至圖片中。多選時，會將所有選取物件的 prompts 插入每張圖，不像角色 / 服裝 / 情緒動作一樣會加入迴圈乘數中",
        "Add": "新增",
        "Add item": "新增條目",
        "Anima Image Set Generator": "Anima套圖產生器",
        "Background": "Background",
        "Category": "分類",
        "Changes saved": "變更已儲存",
        "Characters": "Characters",
        "Checking ComfyUI...": "Checking ComfyUI...",
        "Clear all": "全部取消",
        "Clear objects": "取消物件",
        "Clear outfits": "取消服裝",
        "Click to select an image, or drag an AI image into this area.": "點擊選取圖片，或將 AI 圖片拖曳到此區域。",
        "Click to select an image, or drag the comparison image into this area.": "點擊選取圖片，或將作為比對的圖片拖曳到此區域。",
        "ComfyUI connected": "ComfyUI connected",
        "Custom prompt": "自定義提示詞",
        "Dark": "Dark",
        "Data editor": "資料編輯",
        "Data parsing": "資料解析",
        "Database": "資料庫",
        "Database mapping": "資料庫對應",
        "Delete": "刪除",
        "Denoise": "降噪/Denoise",
        "Display name": "中文名稱",
        "Do not use": "Do not use",
        "Drag to sort": "拖曳排序",
        "Drop image": "Drop image",
        "Edit": "編輯",
        "Emotion / Action": "情緒 / 動作",
        "Enable custom field": "啟用自定義欄位",
        "Enable custom prompt": "自定義提示詞開啟",
        "Enable global negative prompt": "負面全域開啟",
        "Enable global positive prompt": "正面全域開啟",
        "Enable random variation": "啟用隨機差分",
        "Enable variation prompt": "差分提示詞開啟",
        "English": "English",
        "Equipment / Props": "Equipment / Props",
        "Failed to load the model list. Start ComfyUI first.": "模型清單讀取失敗，請先開啟 ComfyUI",
        "Failed to run single-image generation": "單圖執行失敗",
        "Failed to start run": "開始執行失敗",
        "Failed to stop": "停止失敗",
        "Fixed": "固定/Fixed",
        "Fixed reference image": "固定參考圖",
        "Generated image preview": "生成圖片預覽",
        "Generating from this tab ignores image-set selections and outputs a single image only.": "於此分頁生圖時，將會忽略套圖選擇，只進行單圖輸出。",
        "Generation metadata": "生成資料",
        "Global Negative": "Global Negative",
        "Global Positive": "Global Positive",
        "Global prompts": "全域提示詞",
        "Groups": "群組",
        "Height": "高度/Height",
        "Idle": "Idle",
        "Image input": "圖片輸入",
        "Image preview": "圖片預覽",
        "Image set settings": "套圖設定",
        "Increment": "遞增/Increment",
        "Index": "編號",
        "Items": "條目",
        "Light": "Light",
        "Mode": "模式",
        "Model": "模型",
        "Model list refreshed": "模型清單已刷新",
        "Model parameters": "模型參數",
        "Model selection": "模型選擇",
        "Model strength": "模型強度",
        "Model/LoRA model": "模型/LoRA model",
        "Model/UNET": "模型/UNET",
        "Negative": "負面/Negative",
        "Negative prompt": "負面提示詞",
        "New item saved": "新增條目已儲存",
        "No displayable generation-metadata sections were found in this image.": "此圖片沒有析出可顯示的生成資料子區塊。",
        "No image generated yet. The latest result appears after single-image generation finishes.": "尚未生成圖片。完成單圖輸出後，會顯示最新結果。",
        "No image has been loaded. Generation metadata appears after an image is loaded.": "尚未讀取圖片。讀取圖片後，將會顯示生成資料。",
        "No image selected": "尚未選取圖片",
        "No items": "No items",
        "No previous generated image yet.": "尚未有上一張生成圖片。",
        "None": "無",
        "NSFW Display / Invitation": "NSFW Display / Invitation",
        "NSFW Hands / Feet / Breast Interaction": "NSFW Hands / Feet / Breast Interaction",
        "NSFW Lying Positions": "NSFW Lying Positions",
        "NSFW Oral Interaction": "NSFW Oral Interaction",
        "NSFW Riding / Seated": "NSFW Riding / Seated",
        "NSFW Side-Lying / Supported": "NSFW Side-Lying / Supported",
        "NSFW Solo / Toys": "NSFW Solo / Toys",
        "NSFW Standing / Lifted": "NSFW Standing / Lifted",
        "Objects": "物件",
        "Other": "Other",
        "Other data": "其他資料",
        "Outfits": "Outfits",
        "Outfits / Objects": "服裝 / 物件",
        "Output every variation": "差分全輸出",
        "Parameters": "參數",
        "Parse failed:": "解析失敗：",
        "Parse image": "解析圖片",
        "Parsing image metadata...": "正在解析圖片資料...",
        "Positive": "正面/Positive",
        "Positive prompt": "正面提示詞",
        "Previous generated image": "前一張生成的圖",
        "Progress": "執行進度",
        "Prompt": "提示詞",
        "Prompt guidance/CFG": "提示詞權重/CFG",
        "Random": "隨機/Random",
        "Reads ComfyUI and parameter metadata embedded in PNG files.": "系統讀取 PNG 內嵌的 ComfyUI / 參數文字資料",
        "Reference image": "參考圖片",
        "Reference image preview": "參考圖片預覽",
        "Refresh model list": "刷新模型清單",
        "Rename": "改名",
        "Rename preset": "修改預設名稱",
        "Resource usage": "使用資源",
        "Run count": "跑幾次",
        "Running": "Running",
        "Sampler": "採樣器/Sampler",
        "Scheduler": "排程/Scheduler",
        "Search actions": "搜尋動作",
        "Search characters": "搜尋角色",
        "Search data": "搜尋資料",
        "Search objects": "搜尋物件",
        "Search outfits": "搜尋服裝",
        "sec/image": "秒/張",
        "Seconds per image": "出圖秒數",
        "Seed": "種子",
        "Seed mode": "種子模式/Seed mode",
        "Select all": "全選",
        "Select all objects": "全選物件",
        "Select all outfits": "全選服裝",
        "Select background": "背景選擇",
        "Select character": "角色選擇",
        "Select emotion / action": "情緒 / 動作選擇",
        "Select object": "物件選擇",
        "Select outfit": "服裝選擇",
        "Select view": "視圖選擇",
        "SFW Emotion / Action": "SFW Emotion / Action",
        "Single image output preview": "單圖輸出預覽",
        "Start ComfyUI first": "請先開啟 ComfyUI",
        "Start run": "開始執行",
        "Status": "狀態",
        "Steps": "步數/Steps",
        "Stop": "停止",
        "Text encoder/CLIP": "文字編碼/CLIP",
        "Text strength": "文字強度",
        "The parameter and prompt edits below sync directly with Model parameters and the Data editor database.": "以下的參數/prompts調整，將會直接與模型參數/資料編輯的資料庫同步",
        "This field is for visual comparison only and is not used for generation.": "本欄僅供視覺比對，不會參與生圖",
        "Total images this run": "本次總張數",
        "Traditional Chinese": "繁體中文",
        "Tuning comparison": "調校比對",
        "Uncategorized": "Uncategorized",
        "Unknown": "未知",
        "Untitled": "Untitled",
        "Upscale model": "放大模型/Upscale model",
        "Upscale scale": "放大倍率/Upscale scale",
        "Using existing JSON": "沿用現有 JSON",
        "VAE": "變分自編碼器/VAE",
        "Variation prompt": "差分提示詞",
        "View": "View",
        "View / Background / Global prompts": "視圖 / 背景 / 全域",
        "Width": "寬度/Width",
        "• Custom prompt: when the custom field is enabled, this field is appended to each item.": "．自定義提示詞：啟用自定義欄位後，每個條目將會追加此欄位中的內容",
        "• Enable custom field: when checked, inserts the custom field from Emotion / Action into the prompt.": "．啟用自定義欄位：勾選之後，會啟動情緒 / 動作中的自定義欄位，插入提示中",
        "• Image filename format:": "．圖片檔名的格式：",
        "• Key: final output filename.": "．Key值：最後輸出的檔名",
        "• Negative prompt: each item has its own negative prompt; it is inserted only when that item is selected.": "．負面提示詞：每個條目自己的負面提示詞；只有該條目被選用時才會插入",
        "• Variation prompt: separate entries with Enter. When random variation is enabled, one line is randomly inserted.": "．差分提示詞：用Enter分行區隔。啟用隨機差分時，會隨機抽出一行提示詞加進其中",
        "한국어": "한국어"
      },
      "en": {
        ": Appended directly to the image prompt. When multiple objects are selected, all selected object prompts are inserted into every image; they do not increase the loop multiplier like characters, outfits, and actions.": ": Appended directly to the image prompt. When multiple objects are selected, all selected object prompts are inserted into every image; they do not increase the loop multiplier like characters, outfits, and actions.",
        "Add": "Add",
        "Add item": "Add item",
        "Anima Image Set Generator": "Anima Image Set Generator",
        "Background": "Background",
        "Category": "Category",
        "Changes saved": "Changes saved",
        "Characters": "Characters",
        "Checking ComfyUI...": "Checking ComfyUI...",
        "Clear all": "Clear all",
        "Clear objects": "Clear objects",
        "Clear outfits": "Clear outfits",
        "Click to select an image, or drag an AI image into this area.": "Click to select an image, or drag an AI image into this area.",
        "Click to select an image, or drag the comparison image into this area.": "Click to select an image, or drag the comparison image into this area.",
        "ComfyUI connected": "ComfyUI connected",
        "Custom prompt": "Custom prompt",
        "Dark": "Dark",
        "Data editor": "Data editor",
        "Data parsing": "Data parsing",
        "Database": "Database",
        "Database mapping": "Database mapping",
        "Delete": "Delete",
        "Denoise": "Denoise",
        "Display name": "Display name",
        "Do not use": "Do not use",
        "Drag to sort": "Drag to sort",
        "Drop image": "Drop image",
        "Edit": "Edit",
        "Emotion / Action": "Emotion / Action",
        "Enable custom field": "Enable custom field",
        "Enable custom prompt": "Enable custom prompt",
        "Enable global negative prompt": "Enable global negative prompt",
        "Enable global positive prompt": "Enable global positive prompt",
        "Enable random variation": "Enable random variation",
        "Enable variation prompt": "Enable variation prompt",
        "English": "English",
        "Equipment / Props": "Equipment props",
        "Failed to load the model list. Start ComfyUI first.": "Failed to load the model list. Start ComfyUI first.",
        "Failed to run single-image generation": "Failed to run single-image generation",
        "Failed to start run": "Failed to start run",
        "Failed to stop": "Failed to stop",
        "Fixed": "Fixed",
        "Fixed reference image": "Fixed reference image",
        "Generated image preview": "Generated image preview",
        "Generating from this tab ignores image-set selections and outputs a single image only.": "Generating from this tab ignores image-set selections and outputs a single image only.",
        "Generation metadata": "Generation metadata",
        "Global Negative": "Global negative",
        "Global Positive": "Global positive",
        "Global prompts": "Global prompts",
        "Groups": "Groups",
        "Height": "Height",
        "Idle": "Idle",
        "Image input": "Image input",
        "Image preview": "Image preview",
        "Image set settings": "Image set settings",
        "Increment": "Increment",
        "Index": "Index",
        "Items": "Items",
        "Light": "Light",
        "Mode": "Mode",
        "Model": "Model",
        "Model list refreshed": "Model list refreshed",
        "Model parameters": "Model parameters",
        "Model selection": "Model selection",
        "Model strength": "Model strength",
        "Model/LoRA model": "Model/LoRA model",
        "Model/UNET": "Model/UNET",
        "Negative": "Negative",
        "Negative prompt": "Negative prompt",
        "New item saved": "New item saved",
        "No displayable generation-metadata sections were found in this image.": "No displayable generation-metadata sections were found in this image.",
        "No image generated yet. The latest result appears after single-image generation finishes.": "No image generated yet. The latest result appears after single-image generation finishes.",
        "No image has been loaded. Generation metadata appears after an image is loaded.": "No image has been loaded. Generation metadata appears after an image is loaded.",
        "No image selected": "No image selected",
        "No items": "No items",
        "No previous generated image yet.": "No previous generated image yet.",
        "None": "None",
        "NSFW Display / Invitation": "NSFW display/invitation",
        "NSFW Hands / Feet / Breast Interaction": "NSFW hands/feet/breast",
        "NSFW Lying Positions": "NSFW lying positions",
        "NSFW Oral Interaction": "NSFW oral interaction",
        "NSFW Riding / Seated": "NSFW riding/seated",
        "NSFW Side-Lying / Supported": "NSFW side/support",
        "NSFW Solo / Toys": "NSFW solo/toys",
        "NSFW Standing / Lifted": "NSFW standing/lifted",
        "Objects": "Objects",
        "Other": "Other",
        "Other data": "Other data",
        "Outfits": "Outfits",
        "Outfits / Objects": "Outfits / Objects",
        "Output every variation": "Output every variation",
        "Parameters": "Parameters",
        "Parse failed:": "Parse failed: ",
        "Parse image": "Parse image",
        "Parsing image metadata...": "Parsing image metadata...",
        "Positive": "Positive",
        "Positive prompt": "Positive prompt",
        "Previous generated image": "Previous generated image",
        "Progress": "Progress",
        "Prompt": "Prompt",
        "Prompt guidance/CFG": "Prompt guidance/CFG",
        "Random": "Random",
        "Reads ComfyUI and parameter metadata embedded in PNG files.": "Reads ComfyUI and parameter metadata embedded in PNG files.",
        "Reference image": "Reference image",
        "Reference image preview": "Reference image preview",
        "Refresh model list": "Refresh model list",
        "Rename": "Rename",
        "Rename preset": "Rename preset",
        "Resource usage": "Resource usage",
        "Run count": "Run count",
        "Running": "Running",
        "Sampler": "Sampler",
        "Scheduler": "Scheduler",
        "Search actions": "Search actions",
        "Search characters": "Search characters",
        "Search data": "Search data",
        "Search objects": "Search objects",
        "Search outfits": "Search outfits",
        "sec/image": "sec/image",
        "Seconds per image": "Seconds per image",
        "Seed": "Seed",
        "Seed mode": "Seed mode",
        "Select all": "Select all",
        "Select all objects": "Select all objects",
        "Select all outfits": "Select all outfits",
        "Select background": "Select background",
        "Select character": "Select character",
        "Select emotion / action": "Select emotion / action",
        "Select object": "Select object",
        "Select outfit": "Select outfit",
        "Select view": "Select view",
        "SFW Emotion / Action": "SFW emotion/action",
        "Single image output preview": "Single image output preview",
        "Start ComfyUI first": "Start ComfyUI first",
        "Start run": "Start run",
        "Status": "Status",
        "Steps": "Steps",
        "Stop": "Stop",
        "Text encoder/CLIP": "Text encoder/CLIP",
        "Text strength": "Text strength",
        "The parameter and prompt edits below sync directly with Model parameters and the Data editor database.": "The parameter and prompt edits below sync directly with Model parameters and the Data editor database.",
        "This field is for visual comparison only and is not used for generation.": "This field is for visual comparison only and is not used for generation.",
        "Total images this run": "Total images this run",
        "Traditional Chinese": "Traditional Chinese",
        "Tuning comparison": "Tuning comparison",
        "Uncategorized": "Uncategorized",
        "Unknown": "Unknown",
        "Untitled": "Untitled",
        "Upscale model": "Upscale model",
        "Upscale scale": "Upscale scale",
        "Using existing JSON": "Using existing JSON",
        "VAE": "VAE",
        "Variation prompt": "Variation prompt",
        "View": "View",
        "View / Background / Global prompts": "View / Background / Global prompts",
        "Width": "Width",
        "• Custom prompt: when the custom field is enabled, this field is appended to each item.": "• Custom prompt: when the custom field is enabled, this field is appended to each item.",
        "• Enable custom field: when checked, inserts the custom field from Emotion / Action into the prompt.": "• Enable custom field: when checked, inserts the custom field from Emotion / Action into the prompt.",
        "• Image filename format:": "• Image filename format:",
        "• Key: final output filename.": "• Key: final output filename.",
        "• Negative prompt: each item has its own negative prompt; it is inserted only when that item is selected.": "• Negative prompt: each item has its own negative prompt; it is inserted only when that item is selected.",
        "• Variation prompt: separate entries with Enter. When random variation is enabled, one line is randomly inserted.": "• Variation prompt: separate entries with Enter. When random variation is enabled, one line is randomly inserted.",
        "한국어": "한국어"
      },
      "ko": {
        ": Appended directly to the image prompt. When multiple objects are selected, all selected object prompts are inserted into every image; they do not increase the loop multiplier like characters, outfits, and actions.": ": 이미지 프롬프트에 직접 추가됩니다. 여러 오브젝트를 선택하면 선택한 모든 오브젝트 프롬프트가 모든 이미지에 삽입되며, 캐릭터 / 의상 / 감정 동작처럼 반복 배수에 포함되지 않습니다.",
        "Add": "추가",
        "Add item": "항목 추가",
        "Anima Image Set Generator": "Anima 이미지 세트 생성기",
        "Background": "배경",
        "Category": "분류",
        "Changes saved": "변경 사항이 저장되었습니다",
        "Characters": "캐릭터",
        "Checking ComfyUI...": "ComfyUI 확인 중...",
        "Clear all": "모두 해제",
        "Clear objects": "오브젝트 선택 해제",
        "Clear outfits": "의상 선택 해제",
        "Click to select an image, or drag an AI image into this area.": "이미지를 선택하거나 AI 이미지를 이 영역으로 드래그하세요.",
        "Click to select an image, or drag the comparison image into this area.": "이미지를 선택하거나 비교할 이미지를 이 영역으로 드래그하세요.",
        "ComfyUI connected": "ComfyUI 연결됨",
        "Custom prompt": "사용자 지정 프롬프트",
        "Dark": "다크",
        "Data editor": "데이터 편집",
        "Data parsing": "생성 정보 파싱",
        "Database": "데이터베이스",
        "Database mapping": "데이터베이스 매핑",
        "Delete": "삭제",
        "Denoise": "디노이즈",
        "Display name": "표시 이름",
        "Do not use": "사용 안 함",
        "Drag to sort": "드래그하여 정렬",
        "Drop image": "이미지 놓기",
        "Edit": "편집",
        "Emotion / Action": "감정 / 동작",
        "Enable custom field": "사용자 지정 필드 사용",
        "Enable custom prompt": "사용자 지정 프롬프트 사용",
        "Enable global negative prompt": "공통 네거티브 사용",
        "Enable global positive prompt": "공통 포지티브 사용",
        "Enable random variation": "랜덤 변형 사용",
        "Enable variation prompt": "변형 프롬프트 사용",
        "English": "English",
        "Equipment / Props": "장비/소품",
        "Failed to load the model list. Start ComfyUI first.": "모델 목록을 불러오지 못했습니다. 먼저 ComfyUI를 실행하세요.",
        "Failed to run single-image generation": "단일 이미지 생성 실행 실패",
        "Failed to start run": "실행 시작 실패",
        "Failed to stop": "중지 실패",
        "Fixed": "고정",
        "Fixed reference image": "고정 참조 이미지",
        "Generated image preview": "생성 이미지 미리보기",
        "Generating from this tab ignores image-set selections and outputs a single image only.": "이 탭에서 생성하면 이미지 세트 선택을 무시하고 단일 이미지만 출력합니다.",
        "Generation metadata": "생성 정보",
        "Global Negative": "공통 네거티브",
        "Global Positive": "공통 포지티브",
        "Global prompts": "공통 프롬프트",
        "Groups": "그룹",
        "Height": "높이",
        "Idle": "대기 중",
        "Image input": "이미지 입력",
        "Image preview": "이미지 미리보기",
        "Image set settings": "이미지 세트 설정",
        "Increment": "순차 증가",
        "Index": "번호",
        "Items": "항목",
        "Light": "라이트",
        "Mode": "모드",
        "Model": "모델",
        "Model list refreshed": "모델 목록이 새로 고침되었습니다",
        "Model parameters": "모델 파라미터",
        "Model selection": "모델 선택",
        "Model strength": "모델 강도",
        "Model/LoRA model": "모델/LoRA 모델",
        "Model/UNET": "모델/UNET",
        "Negative": "네거티브",
        "Negative prompt": "네거티브 프롬프트",
        "New item saved": "새 항목이 저장되었습니다",
        "No displayable generation-metadata sections were found in this image.": "이 이미지에서 표시할 생성 정보 섹션을 찾지 못했습니다.",
        "No image generated yet. The latest result appears after single-image generation finishes.": "아직 생성된 이미지가 없습니다. 단일 이미지 생성이 완료되면 최신 결과가 표시됩니다.",
        "No image has been loaded. Generation metadata appears after an image is loaded.": "아직 이미지를 불러오지 않았습니다. 이미지를 불러오면 생성 정보가 표시됩니다.",
        "No image selected": "선택된 이미지 없음",
        "No items": "항목 없음",
        "No previous generated image yet.": "이전 생성 이미지가 아직 없습니다.",
        "None": "없음",
        "NSFW Display / Invitation": "NSFW 노출/유도",
        "NSFW Hands / Feet / Breast Interaction": "NSFW 손/발/가슴 상호작용",
        "NSFW Lying Positions": "NSFW 누운 자세",
        "NSFW Oral Interaction": "NSFW 구강 상호작용",
        "NSFW Riding / Seated": "NSFW 올라탄/앉은 자세",
        "NSFW Side-Lying / Supported": "NSFW 옆으로 누운/지탱한 자세",
        "NSFW Solo / Toys": "NSFW 솔로/토이",
        "NSFW Standing / Lifted": "NSFW 선 자세/들어 올림",
        "Objects": "오브젝트",
        "Other": "기타",
        "Other data": "기타 데이터",
        "Outfits": "의상",
        "Outfits / Objects": "의상 / 오브젝트",
        "Output every variation": "모든 변형 출력",
        "Parameters": "파라미터",
        "Parse failed:": "파싱 실패: ",
        "Parse image": "이미지 파싱",
        "Parsing image metadata...": "이미지 정보를 파싱하는 중...",
        "Positive": "포지티브",
        "Positive prompt": "포지티브 프롬프트",
        "Previous generated image": "이전 생성 이미지",
        "Progress": "진행률",
        "Prompt": "프롬프트",
        "Prompt guidance/CFG": "프롬프트 가이던스/CFG",
        "Random": "랜덤",
        "Reads ComfyUI and parameter metadata embedded in PNG files.": "PNG에 내장된 ComfyUI 및 파라미터 메타데이터를 읽습니다.",
        "Reference image": "참조 이미지",
        "Reference image preview": "참조 이미지 미리보기",
        "Refresh model list": "모델 목록 새로 고침",
        "Rename": "이름 변경",
        "Rename preset": "프리셋 이름 변경",
        "Resource usage": "리소스 사용량",
        "Run count": "실행 횟수",
        "Running": "실행 중",
        "Sampler": "샘플러",
        "Scheduler": "스케줄러",
        "Search actions": "동작 검색",
        "Search characters": "캐릭터 검색",
        "Search data": "데이터 검색",
        "Search objects": "오브젝트 검색",
        "Search outfits": "의상 검색",
        "sec/image": "초/장",
        "Seconds per image": "이미지당 소요 시간",
        "Seed": "시드",
        "Seed mode": "시드 모드",
        "Select all": "모두 선택",
        "Select all objects": "오브젝트 모두 선택",
        "Select all outfits": "의상 모두 선택",
        "Select background": "배경 선택",
        "Select character": "캐릭터 선택",
        "Select emotion / action": "감정 / 동작 선택",
        "Select object": "오브젝트 선택",
        "Select outfit": "의상 선택",
        "Select view": "시점 선택",
        "SFW Emotion / Action": "SFW 감정/동작",
        "Single image output preview": "단일 이미지 출력 미리보기",
        "Start ComfyUI first": "먼저 ComfyUI를 실행하세요",
        "Start run": "실행 시작",
        "Status": "상태",
        "Steps": "스텝",
        "Stop": "중지",
        "Text encoder/CLIP": "텍스트 인코더/CLIP",
        "Text strength": "텍스트 강도",
        "The parameter and prompt edits below sync directly with Model parameters and the Data editor database.": "아래 파라미터와 프롬프트 변경 사항은 모델 파라미터 및 데이터 편집 데이터베이스와 바로 동기화됩니다.",
        "This field is for visual comparison only and is not used for generation.": "이 항목은 시각적 비교용이며 이미지 생성에는 사용되지 않습니다.",
        "Total images this run": "이번 실행 총 이미지 수",
        "Traditional Chinese": "번체 중국어",
        "Tuning comparison": "튜닝 비교",
        "Uncategorized": "미분류",
        "Unknown": "알 수 없음",
        "Untitled": "이름 없음",
        "Upscale model": "업스케일 모델",
        "Upscale scale": "업스케일 배율",
        "Using existing JSON": "기존 JSON 사용 중",
        "VAE": "VAE",
        "Variation prompt": "변형 프롬프트",
        "View": "시점",
        "View / Background / Global prompts": "시점 / 배경 / 공통 프롬프트",
        "Width": "너비",
        "• Custom prompt: when the custom field is enabled, this field is appended to each item.": "• 사용자 지정 프롬프트: 사용자 지정 필드를 사용하면 각 항목에 이 필드의 내용이 추가됩니다.",
        "• Enable custom field: when checked, inserts the custom field from Emotion / Action into the prompt.": "• 사용자 지정 필드 사용: 체크하면 감정 / 동작의 사용자 지정 필드가 프롬프트에 삽입됩니다.",
        "• Image filename format:": "• 이미지 파일명 형식:",
        "• Key: final output filename.": "• Key 값: 최종 출력 파일명입니다.",
        "• Negative prompt: each item has its own negative prompt; it is inserted only when that item is selected.": "• 네거티브 프롬프트: 각 항목에 개별 네거티브 프롬프트를 설정합니다. 해당 항목이 선택될 때만 삽입됩니다.",
        "• Variation prompt: separate entries with Enter. When random variation is enabled, one line is randomly inserted.": "• 변형 프롬프트: Enter로 줄을 구분합니다. 랜덤 변형을 사용하면 한 줄을 무작위로 골라 삽입합니다.",
        "한국어": "한국어"
      }
    };
    const UI_LANGS = ["en", "zh-Hant", "ko"];
    const UI_THEMES = ["light", "dark"];
    let currentLanguage = localStorage.getItem("anima_language_clean") || "en";
    let currentTheme = localStorage.getItem("anima_theme_clean") || "dark";
    const i18nTextSources = new WeakMap();

    function uiText(source) {
      const table = UI_TRANSLATIONS[currentLanguage] || UI_TRANSLATIONS["zh-Hant"];
      return table[source] || source;
    }

    function uiRuntimeText(value) {
      let text = String(value || "");
      const table = UI_TRANSLATIONS[currentLanguage] || UI_TRANSLATIONS["zh-Hant"];
      if (table[text]) return table[text];
      ["sec/image", "Parse failed:"].forEach((source) => {
        if (table[source]) text = text.split(source).join(table[source]);
      });
      return text;
    }

    function sourceForText(value) {
      const source = String(value || "").trim();
      return Object.prototype.hasOwnProperty.call(UI_TRANSLATIONS["zh-Hant"], source) ? source : "";
    }

    function translateTextNode(node) {
      const parent = node.parentElement;
      if (!parent || ["SCRIPT", "STYLE", "TEXTAREA", "PRE", "CODE"].includes(parent.tagName)) return;
      const raw = node.nodeValue || "";
      const trimmed = raw.trim();
      if (!trimmed) return;
      let source = i18nTextSources.get(node);
      if (!source) {
        source = sourceForText(trimmed);
        if (!source) return;
        i18nTextSources.set(node, source);
      }
      const prefix = raw.match(/^\s*/)?.[0] || "";
      const suffix = raw.match(/\s*$/)?.[0] || "";
      node.nodeValue = `${prefix}${uiText(source)}${suffix}`;
    }

    function translateAttributes(root = document.body) {
      const attrs = ["placeholder", "title", "alt", "aria-label"];
      const nodes = [root, ...root.querySelectorAll("*")].filter(Boolean);
      nodes.forEach((el) => {
        attrs.forEach((attr) => {
          if (!el.hasAttribute || !el.hasAttribute(attr)) return;
          const dataName = `i18n${attr.replace(/(^|-)([a-z])/g, (_m, _d, ch) => ch.toUpperCase())}Source`;
          let source = el.dataset?.[dataName];
          if (!source) {
            source = sourceForText(el.getAttribute(attr));
            if (!source || !el.dataset) return;
            el.dataset[dataName] = source;
          }
          el.setAttribute(attr, uiText(source));
        });
      });
    }

    function applyI18n(root = document.body) {
      if (!root) return;
      if (!UI_LANGS.includes(currentLanguage)) currentLanguage = "zh-Hant";
      document.documentElement.lang = currentLanguage;
      document.title = uiText("Anima Image Set Generator");
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) translateTextNode(node);
      translateAttributes(root);
      updateHeaderControls();
    }

    function updateHeaderControls() {
      document.querySelectorAll("[data-lang]").forEach((button) => button.classList.toggle("active", button.dataset.lang === currentLanguage));
      document.querySelectorAll("[data-theme]").forEach((button) => button.classList.toggle("active", button.dataset.theme === currentTheme));
    }

    function setLanguage(lang) {
      if (!UI_LANGS.includes(lang)) return;
      currentLanguage = lang;
      localStorage.setItem("anima_language_clean", lang);
      applyI18n();
      updateComfyStatus().catch(() => {});
      updateRunStatus().catch(() => {});
    }

    function applyTheme(theme) {
      if (!UI_THEMES.includes(theme)) theme = "dark";
      currentTheme = theme;
      localStorage.setItem("anima_theme_clean", theme);
      document.body.classList.toggle("theme-light", theme === "light");
      document.body.classList.toggle("theme-dark", theme === "dark");
      updateHeaderControls();
    }

    function bindUiChromeControls() {
      document.querySelectorAll("[data-lang]").forEach((button) => button.onclick = () => setLanguage(button.dataset.lang));
      document.querySelectorAll("[data-theme]").forEach((button) => button.onclick = () => applyTheme(button.dataset.theme));
      applyTheme(currentTheme);
      applyI18n();
    }

    const GLOBAL_SECTIONS = {
      global_positive: "Global Positive",
      global_negative: "Global Negative"
    };
    const ACTION_GROUP_LABELS = {
      0: "SFW Emotion / Action",
      1: "SFW Emotion / Action",
      2: "SFW Emotion / Action",
      3: "NSFW Display / Invitation",
      4: "NSFW Solo / Toys",
      5: "NSFW Oral Interaction",
      6: "NSFW Hands / Feet / Breast Interaction",
      7: "NSFW Lying Positions",
      8: "NSFW Riding / Seated",
      9: "NSFW Standing / Lifted",
      10: "NSFW Side-Lying / Supported"
    };
    const DEFAULT_GROUP_LABELS = {
      characters: "Characters",
      outfits: "Outfits",
      objects: "Equipment / Props",
      actions: "SFW Emotion / Action",
      angles: "View",
      backgrounds: "Background"
    };

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: {"Content-Type": "application/json"},
        ...options
      });
      const data = await response.json();
      if (!response.ok || data.ok === false) throw new Error(data.error || response.statusText);
      return data;
    }

    function activeModelPreset() { return config.model_presets[config.active_model_preset]; }
    function activeLoopPreset() { return library.loop_presets[config.active_loop_preset]; }
    function loopPresetName(index) {
      return library.loop_presets?.[index]?.name || `Preset ${index + 1}`;
    }

    function setMessage(message) {
      const logs = $("logs");
      if (!logs) return;
      const previous = logs.textContent ? "\n" + logs.textContent : "";
      logs.textContent = uiRuntimeText(message) + previous;
    }

    function syncModelInputsFromDom() {
      if (!config || !Array.isArray(config.model_presets)) return;
      const preset = activeModelPreset();
      const s = preset?.settings;
      if (!s) return;
      const singleMode = activeTabName() === "single";
      const ids = singleMode
        ? {
            unet: "singleUnetName", clip: "singleClipName", vae: "singleVaeName",
            sampler: "singleSamplerName", scheduler: "singleSchedulerName", upscale: "singleUpscaleModel",
            width: "singleWidth", height: "singleHeight", steps: "singleSteps", cfg: "singleCfg",
            denoise: "singleDenoise", seed: "singleSeed", seedMode: "singleSeedMode", upscaleScale: "singleUpscaleScale"
          }
        : {
            unet: "unetName", clip: "clipName", vae: "vaeName",
            sampler: "samplerName", scheduler: "schedulerName", upscale: "upscaleModel",
            width: "width", height: "height", steps: "steps", cfg: "cfg",
            denoise: "denoise", seed: "seed", seedMode: "seedMode", upscaleScale: "upscaleScale"
          };
      const read = (id) => { const el = $(id); return el ? el.value : undefined; };
      const readNumber = (id, fallback) => {
        const raw = read(id);
        if (raw === undefined) return fallback;
        if (String(raw).trim() === "") return "";
        const value = Number(raw);
        return Number.isFinite(value) ? value : fallback;
      };
      const unet = read(ids.unet);
      const clip = read(ids.clip);
      const vae = read(ids.vae);
      const sampler = read(ids.sampler);
      const scheduler = read(ids.scheduler);
      const upscale = read(ids.upscale);
      if (unet !== undefined) s.unet_name = unet;
      if (clip !== undefined) s.clip_name = clip;
      if (vae !== undefined) s.vae_name = vae;
      if (sampler !== undefined) s.sampler_name = sampler;
      if (scheduler !== undefined) s.scheduler = scheduler;
      if (upscale !== undefined) ensureUpscale(s).model_name = upscale;
      s.width = readNumber(ids.width, s.width);
      s.height = readNumber(ids.height, s.height);
      s.steps = readNumber(ids.steps, s.steps);
      s.cfg = readNumber(ids.cfg, s.cfg);
      s.denoise = readNumber(ids.denoise, s.denoise ?? "");
      s.seed = readNumber(ids.seed, s.seed);
      const seedMode = read(ids.seedMode);
      if (seedMode !== undefined) s.seed_mode = seedMode;
      ensureUpscale(s).scale_by = readNumber(ids.upscaleScale, s.upscale?.scale_by ?? "");
    }

    function currentModelOverrideForRun() {
      syncModelInputsFromDom();
      const preset = activeModelPreset();
      return {
        active_model_preset: config.active_model_preset,
        settings: JSON.parse(JSON.stringify(preset?.settings || {}))
      };
    }

    function debounceSaveConfig() {
      clearTimeout(configSaveTimer);
      configSaveTimer = setTimeout(() => saveConfig(), 350);
    }

    function debounceSaveLibrary() {
      clearTimeout(librarySaveTimer);
      librarySaveTimer = setTimeout(saveLibraryData, 350);
    }

    async function saveConfig(options = {}) {
      try {
        syncModelInputsFromDom();
        await api("/api/config", {method: "POST", body: JSON.stringify(config)});
        return true;
      } catch (err) {
        const message = "Failed to save settings: " + err.message;
        $("logs").textContent = message;
        if (options.raise) throw new Error(message);
        return false;
      }
    }

    async function saveLibraryData() {
      try {
        await api("/api/library", {method: "POST", body: JSON.stringify(library)});
      } catch (err) {
        $("logs").textContent = "Failed to save database: " + err.message;
      }
    }

    function sortedItems(section) {
      return Object.entries(library[section]).sort((a, b) => {
        const an = a[1].number || "9999";
        const bn = b[1].number || "9999";
        return an.localeCompare(bn, undefined, {numeric: true}) || a[0].localeCompare(b[0]);
      });
    }

    function label(record, key) {
      return record.name || record.display_name || record.zh_name || key;
    }

    function defaultActionGroupTag(record) {
      const sortGroup = Number(record.sort_group ?? 9999);
      return ACTION_GROUP_LABELS[sortGroup] || "Other";
    }

    function normalizeGroupLabel(value) {
      return String(value || "").replaceAll("\u6210\u4eba", "NSFW").trim();
    }

    function ensureGroups(section) {
      if (!library.groups) library.groups = {};
      if (!library.groups[section]) library.groups[section] = {};
      const groups = library.groups[section];
      Object.entries(groups).forEach(([key, group]) => {
        group.name = normalizeGroupLabel(group.name || group.display_name || group.name || key);
        delete group.key;
        delete group.display_name;
      });
      const records = library[section] || {};
      Object.values(records).forEach((record) => {
        if (!record.group) {
          record.group = record.group_key || (section === "objects" ? "equipment" : "default");
          if (section === "actions" && !record.group_key) record.group = safeKey(actionGroupTag(record));
        }
        record.group = safeKey(record.group);
        const legacyGroupTag = record.group_tag;
        record.name = record.name || record.display_name || record.zh_name || "Untitled";
        delete record.key;
        delete record.zh_name;
        delete record.display_name;
        delete record.group_key;
        delete record.group_tag;
        delete record.sort_group;
        delete record.sort_category;
        if (!groups[record.group]) {
          groups[record.group] = {
            name: normalizeGroupLabel(legacyGroupTag || DEFAULT_GROUP_LABELS[section] || "Uncategorized"),
            sort_index: Object.keys(groups).length + 1
          };
        }
      });
      if (!Object.keys(groups).length) {
        const key = section === "objects" ? "equipment" : "default";
        groups[key] = {name: DEFAULT_GROUP_LABELS[section] || "Uncategorized", sort_index: 1};
      }
      return groups;
    }

    function groupEntries(section) {
      const groups = ensureGroups(section);
      return Object.entries(groups).sort((a, b) => {
        const ai = Number(a[1].sort_index ?? 9999);
        const bi = Number(b[1].sort_index ?? 9999);
        return ai - bi || groupLabel(section, a[0]).localeCompare(groupLabel(section, b[0]));
      });
    }

    function groupLabel(section, groupKey, record = null) {
      const group = library.groups?.[section]?.[groupKey];
      const raw = group?.name || group?.display_name || record?.group_tag || DEFAULT_GROUP_LABELS[section] || groupKey || "Uncategorized";
      return normalizeGroupLabel(raw);
    }

    function groupSortIndex(section, groupKey) {
      const group = ensureGroups(section)[groupKey];
      const index = Number(group?.sort_index);
      return Number.isFinite(index) ? index : 9999;
    }

    function recordKeysForGroup(section, groupKey) {
      return sortedRecordEntries(library[section] || {}, section)
        .filter(([_key, record]) => recordGroupKey(section, record) === groupKey)
        .map(([key]) => key);
    }

    function nextRecordSortIndex(section, groupKey) {
      return Math.max(
        0,
        ...Object.values(library[section] || {})
          .filter((record) => recordGroupKey(section, record) === groupKey)
          .map((record) => Number(record.sort_index || 0))
          .filter((index) => Number.isFinite(index))
      );
    }

    function applyRecordOrderFields(section, record, groupKey, sortIndex = null) {
      record.group = groupKey;
      delete record.key;
      delete record.zh_name;
      delete record.display_name;
      delete record.group_key;
      delete record.group_tag;
      delete record.sort_group;
      delete record.sort_category;
      if (sortIndex !== null) record.sort_index = sortIndex;
      else if (!Number.isFinite(Number(record.sort_index))) {
        record.sort_index = nextRecordSortIndex(section, groupKey) + 1;
      }
    }

    function reindexRecordsInGroup(section, groupKey, orderedKeys = null) {
      const currentKeys = recordKeysForGroup(section, groupKey);
      const currentSet = new Set(currentKeys);
      const keys = uniqueKeys([...(orderedKeys || []), ...currentKeys]).filter((key) => currentSet.has(key));
      keys.forEach((key, index) => {
        const record = library[section]?.[key];
        if (record && recordGroupKey(section, record) === groupKey) {
          applyRecordOrderFields(section, record, groupKey, index + 1);
        }
      });
    }

    function reindexSectionRecordsByGroups(section) {
      groupEntries(section).forEach(([groupKey]) => reindexRecordsInGroup(section, groupKey));
    }

    function uniqueKeys(keys) {
      const seen = new Set();
      return (keys || []).filter((key) => {
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      });
    }

    function reorderKeys(keys, sourceKey, targetKey, placeAfter) {
      const base = uniqueKeys(keys);
      if (sourceKey === targetKey || !base.includes(sourceKey) || !base.includes(targetKey)) return base;
      const ordered = base.filter((key) => key !== sourceKey);
      const targetIndex = ordered.indexOf(targetKey);
      if (targetIndex < 0) return base;
      ordered.splice(targetIndex + (placeAfter ? 1 : 0), 0, sourceKey);
      return uniqueKeys(ordered);
    }

    function mergeOrderedSubset(currentKeys, orderedSubsetKeys) {
      const current = uniqueKeys(currentKeys);
      const currentSet = new Set(current);
      const subset = uniqueKeys(orderedSubsetKeys).filter((key) => currentSet.has(key));
      if (!subset.length) return current;
      const subsetSet = new Set(subset);
      let subsetIndex = 0;
      return current.map((key) => subsetSet.has(key) ? subset[subsetIndex++] : key);
    }

    function dragPlaceAfter(event, target) {
      const rect = target.getBoundingClientRect();
      return event.clientY > rect.top + rect.height / 2;
    }

    function markDbDragEnded() {
      dbDragJustEnded = true;
      window.setTimeout(() => { dbDragJustEnded = false; }, 160);
    }

    function setDbItemContent(button, text, draggable = false) {
      button.innerHTML = "";
      if (draggable) {
        const handle = document.createElement("span");
        handle.className = "drag-handle";
        handle.textContent = "::";
        handle.title = uiText("Drag to sort");
        button.appendChild(handle);
      }
      const labelEl = document.createElement("span");
      labelEl.className = "db-item-label";
      labelEl.textContent = text;
      button.appendChild(labelEl);
    }

    function dbDragOrderFrom(container, dragScope) {
      if (!container) return [];
      return uniqueKeys(Array.from(container.children)
        .filter((child) => child?.dataset?.dbDragScope === dragScope && child.dataset.dbDragKey)
        .map((child) => child.dataset.dbDragKey));
    }

    function dbDragTargetFromPoint(clientX, clientY, container, dragScope, sourceEl) {
      if (!container || typeof document.elementFromPoint !== "function") return null;
      let target = document.elementFromPoint(clientX, clientY)?.closest?.(".db-item[data-db-drag-key]");
      if (target === sourceEl) {
        const hidden = sourceEl.style.pointerEvents;
        sourceEl.style.pointerEvents = "none";
        target = document.elementFromPoint(clientX, clientY)?.closest?.(".db-item[data-db-drag-key]");
        sourceEl.style.pointerEvents = hidden;
      }
      if (!target || target === sourceEl || target.parentElement !== container || target.dataset.dbDragScope !== dragScope) return null;
      return target;
    }

    function clearDbDragOver(container) {
      container?.querySelectorAll?.(".db-item.drag-over")?.forEach((item) => item.classList.remove("drag-over"));
    }

    function moveDbDraggedItem(event, container, dragScope) {
      const context = dbDragContext;
      if (!context || context.scope !== dragScope || context.parent !== container) return false;
      const sourceEl = context.element;
      if (!sourceEl || sourceEl.parentElement !== container) return false;
      event.preventDefault();
      const target = dbDragTargetFromPoint(event.clientX, event.clientY, container, dragScope, sourceEl);
      clearDbDragOver(container);
      if (!target) return true;
      target.classList.add("drag-over");
      const placeAfter = dragPlaceAfter(event, target);
      const reference = placeAfter ? target.nextElementSibling : target;
      if (reference !== sourceEl && sourceEl.nextElementSibling !== reference) {
        container.insertBefore(sourceEl, reference);
        context.moved = true;
      }
      return true;
    }

    function commitDbDragOrder() {
      const context = dbDragContext;
      if (!context || context.done) return false;
      const orderedKeys = dbDragOrderFrom(context.parent, context.scope);
      if (!orderedKeys.length || !orderedKeys.includes(context.key)) return false;
      const originalKeys = uniqueKeys(context.originalKeys || []);
      const unchanged = orderedKeys.length === originalKeys.length && orderedKeys.every((key, index) => key === originalKeys[index]);
      context.done = true;
      if (!unchanged) context.onReorder(context.key, "", false, orderedKeys);
      return !unchanged;
    }

    function cleanupDbPointerDrag(markEnded = true) {
      const context = dbDragContext;
      if (!context) return;
      if (context.moveHandler) document.removeEventListener("pointermove", context.moveHandler, true);
      if (context.upHandler) document.removeEventListener("pointerup", context.upHandler, true);
      if (context.cancelHandler) document.removeEventListener("pointercancel", context.cancelHandler, true);
      try { context.handle?.releasePointerCapture?.(context.pointerId); } catch (_err) {}
      context.element?.classList?.remove("dragging", "drag-over");
      context.parent?.classList?.remove("drag-sorting");
      clearDbDragOver(context.parent);
      dbDragContext = null;
      if (markEnded && context.active) markDbDragEnded();
    }

    function bindDbDragContainer(container, dragScope, onReorder) {
      if (!container) return;
      container._dbDragScope = dragScope;
      container._dbDragReorder = onReorder;
      if (container._dbDragOverHandler) container.removeEventListener("dragover", container._dbDragOverHandler);
      if (container._dbDropHandler) container.removeEventListener("drop", container._dbDropHandler);
      if (container._dbDragLeaveHandler) container.removeEventListener("dragleave", container._dbDragLeaveHandler);
      container._dbDragOverHandler = null;
      container._dbDropHandler = null;
      container._dbDragLeaveHandler = null;
    }

    function bindDbDragSort(button, key, onReorder, dragScope = "db-item") {
      button.draggable = false;
      button.classList.add("sortable");
      button.dataset.dbDragKey = key;
      button.dataset.dbDragScope = dragScope;
      const handle = button.querySelector(".drag-handle") || button;
      handle.addEventListener("pointerdown", (event) => {
        if (event.button !== 0 || dbDragContext) return;
        if (!applyDbEditor({rerender: false, silent: true})) return;
        const parent = button.parentElement;
        if (!parent) return;
        event.preventDefault();
        event.stopPropagation();
        dbDragContext = {
          scope: dragScope,
          key,
          element: button,
          parent,
          handle,
          pointerId: event.pointerId,
          startX: event.clientX,
          startY: event.clientY,
          onReorder,
          originalKeys: dbDragOrderFrom(parent, dragScope),
          moved: false,
          active: false,
          done: false,
          moveHandler: null,
          upHandler: null,
          cancelHandler: null,
        };
        try { handle.setPointerCapture?.(event.pointerId); } catch (_err) {}
        dbDragContext.moveHandler = (moveEvent) => {
          const context = dbDragContext;
          if (!context || context.pointerId !== moveEvent.pointerId) return;
          const movedFarEnough = Math.abs(moveEvent.clientY - context.startY) > 3 || Math.abs(moveEvent.clientX - context.startX) > 3;
          if (!context.active && !movedFarEnough) return;
          if (!context.active) {
            context.active = true;
            context.element.classList.add("dragging");
            context.parent.classList.add("drag-sorting");
          }
          moveDbDraggedItem(moveEvent, context.parent, context.scope);
        };
        dbDragContext.upHandler = (upEvent) => {
          const context = dbDragContext;
          if (!context || context.pointerId !== upEvent.pointerId) return;
          upEvent.preventDefault();
          if (context.active) commitDbDragOrder();
          cleanupDbPointerDrag(true);
        };
        dbDragContext.cancelHandler = (cancelEvent) => {
          const context = dbDragContext;
          if (!context || context.pointerId !== cancelEvent.pointerId) return;
          cleanupDbPointerDrag(true);
        };
        document.addEventListener("pointermove", dbDragContext.moveHandler, true);
        document.addEventListener("pointerup", dbDragContext.upHandler, true);
        document.addEventListener("pointercancel", dbDragContext.cancelHandler, true);
      });
    }

    function actionGroupTag(record) {
      const tag = normalizeGroupLabel(record.group_tag || record.group || "");
      if (tag) return tag;
      return defaultActionGroupTag(record);
    }

    function isGlobalSection(section) {
      return Object.prototype.hasOwnProperty.call(GLOBAL_SECTIONS, section);
    }

    function usesEditableKey(section) {
      return !isGlobalSection(section) && !["angles", "backgrounds"].includes(section);
    }

    function numericOrBlank(value) {
      if (value === undefined || value === null || String(value).trim() === "") return "";
      const number = Number(value);
      return Number.isFinite(number) ? number : "";
    }

    function positiveInt(value, fallback = 0) {
      const number = Math.trunc(Number(value));
      return Number.isFinite(number) && number > 0 ? number : fallback;
    }

    function selectedLibraryCount(section, selectedKeys) {
      const selected = new Set(selectedKeys || []);
      return Object.keys(library?.[section] || {}).filter((key) => selected.has(key)).length;
    }

    function randomPromptLines(record) {
      return String(record?.random_prompt || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    }

    function randomPromptChoiceCount(record) {
      return randomPromptLines(record).length;
    }

    function computeRawTotal() {
      const loop = activeLoopPreset().settings;
      const repeat = positiveInt(config.run.repeat_count, 1);
      const characters = selectedLibraryCount("characters", loop.characters);
      const outfits = selectedLibraryCount("outfits", loop.outfits);
      const selectedActions = new Set(loop.actions || []);
      const actionUnits = Object.entries(library?.actions || {}).reduce((total, [key, record]) => {
        if (!selectedActions.has(key)) return total;
        if (loop.include_random !== false && loop.random_prompt_mode === "all") {
          return total + Math.max(1, randomPromptChoiceCount(record));
        }
        return total + 1;
      }, 0);
      return characters * outfits * actionUnits * repeat;
    }

    function computeTotal() {
      const rawTotal = computeRawTotal();
      const startIndex = positiveInt(config.run.start_index, 1);
      const limit = positiveInt(config.run.limit, 0);
      const available = Math.max(0, rawTotal - startIndex + 1);
      return limit ? Math.min(available, limit) : available;
    }

    function renderPresetButtons(kind) {
      const holder = kind === "model" ? $("modelPresetButtons") : $("loopPresetButtons");
      const presets = kind === "model" ? config.model_presets : library.loop_presets;
      const active = kind === "model" ? config.active_model_preset : config.active_loop_preset;
      holder.innerHTML = "";
      presets.forEach((preset, index) => {
        const button = document.createElement("button");
        button.textContent = kind === "model" ? preset.name : loopPresetName(index);
        button.className = index === active ? `active ${kind}` : "";
        button.onclick = () => {
          if (kind === "model") config.active_model_preset = index;
          else config.active_loop_preset = index;
          debounceSaveConfig();
          renderAll();
        };
        holder.appendChild(button);
      });
    }

    function renderModelTab() {
      renderPresetButtons("model");
      const preset = activeModelPreset();
      const s = preset.settings;
      renderRequiredModelSelect("unetName", ["diffusion_models"], s.unet_name || "", (value) => { s.unet_name = value; debounceSaveConfig(); });
      renderRequiredModelSelect("clipName", ["text_encoders", "clip"], s.clip_name || "", (value) => { s.clip_name = value; debounceSaveConfig(); });
      renderRequiredModelSelect("vaeName", ["vae"], s.vae_name || "", (value) => { s.vae_name = value; debounceSaveConfig(); });
      renderModelSelect("samplerName", (modelLists._samplers || []).length ? modelLists._samplers : fallbackSamplers(), s.sampler_name || "", (value) => { s.sampler_name = value; debounceSaveConfig(); }, true, false);
      renderModelSelect("schedulerName", (modelLists._schedulers || []).length ? modelLists._schedulers : fallbackSchedulers(), s.scheduler || "", (value) => { s.scheduler = value; debounceSaveConfig(); }, true, false);
      renderOptionalModelSelect("upscaleModel", ["upscale_models"], s.upscale?.model_name || "", (value) => { ensureUpscale(s).model_name = value; debounceSaveConfig(); });
      $("upscaleScale").value = s.upscale?.scale_by ?? "";
      $("width").value = s.width;
      $("height").value = s.height;
      $("steps").value = s.steps;
      $("cfg").value = s.cfg;
      $("denoise").value = s.denoise ?? "";
      $("seed").value = s.seed;
      $("seedMode").value = s.seed_mode;
      $("loraRows").innerHTML = "";
      s.loras.forEach((lora, index) => {
        const row = document.createElement("div");
        row.className = "lora-row";
        lora.positive_prompt = lora.positive_prompt || "";
        lora.negative_prompt = lora.negative_prompt || "";
        row.classList.toggle("lora-disabled", !lora.enabled);
        row.innerHTML = `
          <input type="checkbox" ${lora.enabled ? "checked" : ""}>
          <label class="lora-field"><span>Model/LoRA model</span><select></select></label>
          <label class="lora-field"><span>Model strength</span><input type="number" step="0.05" value="${lora.strength_model}"></label>
          <label class="lora-field"><span>Text strength</span><input type="number" step="0.05" value="${lora.strength_clip}"></label>
          <label class="lora-field lora-prompt-field"><span>Positive</span><textarea>${escapeHtml(lora.positive_prompt)}</textarea></label>
          <label class="lora-field lora-prompt-field"><span>Negative</span><textarea>${escapeHtml(lora.negative_prompt)}</textarea></label>
        `;
        const inputs = row.querySelectorAll("input");
        const textareas = row.querySelectorAll("textarea");
        const select = row.querySelector("select");
        fillSelect(select, modelValues(["loras"]), lora.lora_name || "", true);
        inputs[0].onchange = () => {
          lora.enabled = inputs[0].checked;
          row.classList.toggle("lora-disabled", !lora.enabled);
          debounceSaveConfig();
        };
        select.onchange = () => { lora.lora_name = select.value; debounceSaveConfig(); };
        inputs[1].oninput = () => { lora.strength_model = numericOrBlank(inputs[1].value); debounceSaveConfig(); };
        inputs[2].oninput = () => { lora.strength_clip = numericOrBlank(inputs[2].value); debounceSaveConfig(); };
        textareas[0].oninput = () => { lora.positive_prompt = textareas[0].value; debounceSaveConfig(); };
        textareas[1].oninput = () => { lora.negative_prompt = textareas[1].value; debounceSaveConfig(); };
        $("loraRows").appendChild(row);
      });
    }

    function ensureUpscale(settings) {
      if (!settings.upscale) settings.upscale = {enabled: false, model_name: ""};
      return settings.upscale;
    }

    function singleSettings() {
      if (!config.single_image) {
        config.single_image = {
          source_mode: "previous",
          use_global_positive: false,
          use_global_negative: false,
          use_action_random_prompt: false,
          action_random_index: 1,
          use_action_custom_prompt: false,
          character: "",
          outfit: "",
          action: "",
          angle: "",
          background: "",
          object: ""
        };
      }
      const single = config.single_image;
      single.source_mode = single.source_mode || "previous";
      delete single.positive_prompt;
      delete single.negative_prompt;
      delete single.filename_prefix;
      if (single.use_global_positive === undefined) single.use_global_positive = false;
      if (single.use_global_negative === undefined) single.use_global_negative = false;
      if (single.use_action_random_prompt === undefined) single.use_action_random_prompt = false;
      if (single.use_action_custom_prompt === undefined) single.use_action_custom_prompt = false;
      single.action_random_index = positiveInt(single.action_random_index, 1);
      const ensureKey = (field, section, allowBlank = false) => {
        const records = library?.[section] || {};
        if (single[field] && records[single[field]]) return;
        const keys = Object.keys(records);
        single[field] = allowBlank ? (single[field] || "") : (keys[0] || "");
      };
      ensureKey("character", "characters");
      ensureKey("outfit", "outfits");
      ensureKey("action", "actions");
      ensureKey("angle", "angles");
      ensureKey("background", "backgrounds");
      ensureKey("object", "objects", true);
      return single;
    }

    function renderSinglePresetButtons() {
      const holder = $("singleModelPresetButtons");
      if (!holder) return;
      holder.innerHTML = "";
      config.model_presets.forEach((preset, index) => {
        const button = document.createElement("button");
        button.textContent = preset.name;
        button.className = index === config.active_model_preset ? "active model" : "";
        button.onclick = () => {
          config.active_model_preset = index;
          debounceSaveConfig();
          renderAll();
        };
        holder.appendChild(button);
      });
    }

    function renderLoraEditorRows(holderId, settings) {
      const holder = $(holderId);
      if (!holder) return;
      holder.innerHTML = "";
      if (!Array.isArray(settings.loras)) settings.loras = [];
      while (settings.loras.length < 5) {
        settings.loras.push({enabled: false, lora_name: "", strength_model: 0.8, strength_clip: 0.8, positive_prompt: "", negative_prompt: ""});
      }
      settings.loras.forEach((lora) => {
        const row = document.createElement("div");
        row.className = "lora-row";
        lora.positive_prompt = lora.positive_prompt || "";
        lora.negative_prompt = lora.negative_prompt || "";
        row.classList.toggle("lora-disabled", !lora.enabled);
        row.innerHTML = `
          <input type="checkbox" ${lora.enabled ? "checked" : ""}>
          <label class="lora-field"><span>Model/LoRA model</span><select></select></label>
          <label class="lora-field"><span>Model strength</span><input type="number" step="0.05" value="${lora.strength_model}"></label>
          <label class="lora-field"><span>Text strength</span><input type="number" step="0.05" value="${lora.strength_clip}"></label>
          <label class="lora-field lora-prompt-field"><span>Positive</span><textarea>${escapeHtml(lora.positive_prompt)}</textarea></label>
          <label class="lora-field lora-prompt-field"><span>Negative</span><textarea>${escapeHtml(lora.negative_prompt)}</textarea></label>
        `;
        const inputs = row.querySelectorAll("input");
        const textareas = row.querySelectorAll("textarea");
        const select = row.querySelector("select");
        fillSelect(select, modelValues(["loras"]), lora.lora_name || "", true);
        inputs[0].onchange = () => {
          lora.enabled = inputs[0].checked;
          row.classList.toggle("lora-disabled", !lora.enabled);
          debounceSaveConfig();
        };
        select.onchange = () => { lora.lora_name = select.value; debounceSaveConfig(); };
        inputs[1].oninput = () => { lora.strength_model = numericOrBlank(inputs[1].value); debounceSaveConfig(); };
        inputs[2].oninput = () => { lora.strength_clip = numericOrBlank(inputs[2].value); debounceSaveConfig(); };
        textareas[0].oninput = () => { lora.positive_prompt = textareas[0].value; debounceSaveConfig(); };
        textareas[1].oninput = () => { lora.negative_prompt = textareas[1].value; debounceSaveConfig(); };
        holder.appendChild(row);
      });
    }

    function singleRecord(section, key) {
      const records = library?.[section] || {};
      return records?.[key] || {};
    }

    function renderSingleActionSelect(single, forceOpen = false) {
      const select = $("singleActionSelect");
      if (!select) return;
      const filterInput = $("singleActionFilter");
      const filter = (filterInput?.value || "").trim().toLowerCase();
      const isFiltering = !!filter;
      let entries = sortedRecordEntries(library.actions || {}, "actions").filter(([key, record]) => {
        if (!filter) return true;
        const text = [
          key,
          label(record, key),
          record.name || "",
          record.display_name || "",
          record.group || "",
          record.prompt || "",
          record.negative_prompt || "",
          record.random_prompt || "",
          record.custom_prompt || "",
        ].join(" ").toLowerCase();
        return text.includes(filter);
      });
      if (!isFiltering && single.action && library.actions?.[single.action] && !entries.some(([key]) => key === single.action)) {
        entries = [[single.action, library.actions[single.action]], ...entries];
      }
      select.innerHTML = "";
      entries.forEach(([key, record]) => {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = label(record, key);
        option.selected = key === single.action;
        select.appendChild(option);
      });
      const shouldOpen = forceOpen || isFiltering;
      if (shouldOpen) {
        select.size = String(Math.max(2, Math.min(entries.length || 1, 8)));
        select.classList.add("single-select-expanded");
        if (!entries.some(([key]) => key === single.action)) select.selectedIndex = -1;
      } else {
        select.size = 1;
        select.classList.remove("single-select-expanded");
      }
      select.onchange = () => {
        single.action = select.value;
        if (filterInput) filterInput.value = "";
        debounceSaveConfig();
        renderSinglePromptEditor();
      };
    }

    function renderSinglePromptEditor() {
      const single = singleSettings();
      $("singleUseGlobalPositive").checked = !!single.use_global_positive;
      $("singleUseGlobalNegative").checked = !!single.use_global_negative;
      $("singleGlobalPositive").value = library.defaults?.global_positive || "";
      $("singleGlobalNegative").value = library.defaults?.global_negative || "";

      renderSelect("singleAngleSelect", library.angles, single.angle, (value) => { single.angle = value; debounceSaveConfig(); renderSinglePromptEditor(); });
      renderSelect("singleBackgroundSelect", library.backgrounds, single.background, (value) => { single.background = value; debounceSaveConfig(); renderSinglePromptEditor(); });
      renderSelect("singleCharacterSelect", library.characters, single.character, (value) => { single.character = value; debounceSaveConfig(); renderSinglePromptEditor(); });
      renderSingleActionSelect(single);
      renderSelect("singleOutfitSelect", library.outfits, single.outfit, (value) => { single.outfit = value; debounceSaveConfig(); renderSinglePromptEditor(); });
      renderSelect("singleObjectSelect", library.objects || {}, single.object || "", (value) => { single.object = value; debounceSaveConfig(); renderSinglePromptEditor(); }, true);

      const angle = singleRecord("angles", single.angle);
      const background = singleRecord("backgrounds", single.background);
      const character = singleRecord("characters", single.character);
      const action = singleRecord("actions", single.action);
      const outfit = singleRecord("outfits", single.outfit);
      const objectRecord = single.object ? singleRecord("objects", single.object) : {};

      $("singleAnglePrompt").value = angle.prompt || "";
      $("singleAngleNegativePrompt").value = angle.negative_prompt || "";
      $("singleBackgroundPrompt").value = background.prompt || "";
      $("singleBackgroundNegativePrompt").value = background.negative_prompt || "";
      $("singleCharacterPrompt").value = character.prompt || "";
      $("singleCharacterNegativePrompt").value = character.negative_prompt || "";
      $("singleActionPrompt").value = action.prompt || "";
      $("singleActionNegativePrompt").value = action.negative_prompt || "";
      const actionRandomLines = randomPromptLines(action);
      const actionRandomCount = actionRandomLines.length;
      if (actionRandomCount) {
        single.action_random_index = Math.max(1, Math.min(positiveInt(single.action_random_index, 1), actionRandomCount));
      } else {
        single.action_random_index = 1;
      }
      $("singleActionRandomEnabled").checked = !!single.use_action_random_prompt;
      const randomIndexSelect = $("singleActionRandomIndex");
      randomIndexSelect.innerHTML = "";
      if (actionRandomCount) {
        for (let index = 1; index <= actionRandomCount; index += 1) {
          const option = document.createElement("option");
          option.value = String(index);
          option.textContent = String(index);
          option.selected = index === single.action_random_index;
          randomIndexSelect.appendChild(option);
        }
        randomIndexSelect.disabled = false;
      } else {
        const option = document.createElement("option");
        option.value = "1";
        option.textContent = uiText("None");
        randomIndexSelect.appendChild(option);
        randomIndexSelect.disabled = true;
      }
      $("singleActionRandomCount").textContent = actionRandomCount ? `/ ${actionRandomCount}` : "/ 0";
      $("singleActionRandomPrompt").value = single.use_action_random_prompt && actionRandomCount ? actionRandomLines[single.action_random_index - 1] : "";
      $("singleActionCustomEnabled").checked = !!single.use_action_custom_prompt;
      $("singleActionCustomPrompt").value = action.custom_prompt || "";
      $("singleOutfitPrompt").value = outfit.prompt || "";
      $("singleOutfitNegativePrompt").value = outfit.negative_prompt || "";
      $("singleObjectPrompt").value = objectRecord.prompt || "";
      $("singleObjectNegativePrompt").value = objectRecord.negative_prompt || "";
    }

    function bindSinglePromptLibraryFields() {
      const bindRecord = (section, field, inputId) => {
        const el = $(inputId);
        if (!el) return;
        el.oninput = () => {
          const key = singleSettings()[field];
          if (!key) return;
          const record = library[section]?.[key];
          if (!record) return;
          if (inputId.endsWith("NegativePrompt")) record.negative_prompt = el.value;
          else if (inputId === "singleActionRandomPrompt") record.random_prompt = el.value;
          else if (inputId === "singleActionCustomPrompt") record.custom_prompt = el.value;
          else record.prompt = el.value;
          debounceSaveLibrary();
        };
      };
      $("singleUseGlobalPositive").onchange = () => { singleSettings().use_global_positive = $("singleUseGlobalPositive").checked; debounceSaveConfig(); };
      $("singleUseGlobalNegative").onchange = () => { singleSettings().use_global_negative = $("singleUseGlobalNegative").checked; debounceSaveConfig(); };
      $("singleGlobalPositive").oninput = () => { library.defaults.global_positive = $("singleGlobalPositive").value; debounceSaveLibrary(); };
      $("singleGlobalNegative").oninput = () => { library.defaults.global_negative = $("singleGlobalNegative").value; debounceSaveLibrary(); };
      if ($("singleActionFilter")) $("singleActionFilter").oninput = () => {
        const hasFilter = $("singleActionFilter").value.trim().length > 0;
        renderSingleActionSelect(singleSettings(), hasFilter);
      };
      bindRecord("angles", "angle", "singleAnglePrompt");
      bindRecord("angles", "angle", "singleAngleNegativePrompt");
      bindRecord("backgrounds", "background", "singleBackgroundPrompt");
      bindRecord("backgrounds", "background", "singleBackgroundNegativePrompt");
      bindRecord("characters", "character", "singleCharacterPrompt");
      bindRecord("characters", "character", "singleCharacterNegativePrompt");
      bindRecord("actions", "action", "singleActionPrompt");
      bindRecord("actions", "action", "singleActionNegativePrompt");
      if ($("singleActionRandomEnabled")) $("singleActionRandomEnabled").onchange = () => {
        singleSettings().use_action_random_prompt = $("singleActionRandomEnabled").checked;
        debounceSaveConfig();
        renderSinglePromptEditor();
      };
      if ($("singleActionRandomIndex")) $("singleActionRandomIndex").onchange = () => {
        singleSettings().action_random_index = positiveInt($("singleActionRandomIndex").value, 1);
        debounceSaveConfig();
        renderSinglePromptEditor();
      };
      if ($("singleActionCustomEnabled")) $("singleActionCustomEnabled").onchange = () => {
        singleSettings().use_action_custom_prompt = $("singleActionCustomEnabled").checked;
        debounceSaveConfig();
      };
      bindRecord("actions", "action", "singleActionCustomPrompt");
      bindRecord("outfits", "outfit", "singleOutfitPrompt");
      bindRecord("outfits", "outfit", "singleOutfitNegativePrompt");
      bindRecord("objects", "object", "singleObjectPrompt");
      bindRecord("objects", "object", "singleObjectNegativePrompt");
    }

    function renderSingleTab() {
      if (!$("tab-single")) return;
      const single = singleSettings();
      const preset = activeModelPreset();
      const s = preset.settings;
      renderSinglePresetButtons();
      $("singleSourceMode").value = single.source_mode || "previous";
      renderRequiredModelSelect("singleUnetName", ["diffusion_models"], s.unet_name || "", (value) => { s.unet_name = value; debounceSaveConfig(); });
      renderRequiredModelSelect("singleClipName", ["text_encoders", "clip"], s.clip_name || "", (value) => { s.clip_name = value; debounceSaveConfig(); });
      renderRequiredModelSelect("singleVaeName", ["vae"], s.vae_name || "", (value) => { s.vae_name = value; debounceSaveConfig(); });
      renderModelSelect("singleSamplerName", (modelLists._samplers || []).length ? modelLists._samplers : fallbackSamplers(), s.sampler_name || "", (value) => { s.sampler_name = value; debounceSaveConfig(); }, true, false);
      renderModelSelect("singleSchedulerName", (modelLists._schedulers || []).length ? modelLists._schedulers : fallbackSchedulers(), s.scheduler || "", (value) => { s.scheduler = value; debounceSaveConfig(); }, true, false);
      renderOptionalModelSelect("singleUpscaleModel", ["upscale_models"], s.upscale?.model_name || "", (value) => { ensureUpscale(s).model_name = value; debounceSaveConfig(); });
      $("singleWidth").value = s.width;
      $("singleHeight").value = s.height;
      $("singleSteps").value = s.steps;
      $("singleCfg").value = s.cfg;
      $("singleDenoise").value = s.denoise ?? "";
      $("singleSeed").value = s.seed;
      $("singleSeedMode").value = s.seed_mode;
      $("singleUpscaleScale").value = s.upscale?.scale_by ?? "";
      renderSinglePromptEditor();
      renderLoraEditorRows("singleLoraRows", s);
      bindSinglePromptLibraryFields();
    }

    function setSingleSourceImage(file) {
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        singleSourceImageData = String(reader.result || "");
        singleSourceFileName = file.name || "single_input.png";
        const zone = $("singleImageDropZone");
        if (zone) zone.classList.add("has-image");
        if ($("singleInputPreview")) $("singleInputPreview").src = singleSourceImageData;
        if ($("singleInputFileName")) $("singleInputFileName").textContent = singleSourceFileName;
      };
      reader.readAsDataURL(file);
    }

    function bindSingleImageInputs() {
      const dropZone = $("singleImageDropZone");
      const input = $("singleImageFileInput");
      if (!dropZone || !input) return;
      input.onchange = () => setSingleSourceImage(input.files?.[0]);
      ["dragenter", "dragover"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
          event.preventDefault();
          event.stopPropagation();
          dropZone.classList.add("drag-over");
        });
      });
      ["dragleave", "dragend", "drop"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
          event.preventDefault();
          event.stopPropagation();
          if (eventName !== "drop") dropZone.classList.remove("drag-over");
        });
      });
      dropZone.addEventListener("drop", (event) => {
        dropZone.classList.remove("drag-over");
        const file = Array.from(event.dataTransfer?.files || []).find((item) => item.type.startsWith("image/"));
        if (file) setSingleSourceImage(file);
      });
    }

    function clearSingleReferenceImage(message = uiText("No previous generated image yet.")) {
      singleSourceImageData = "";
      singleSourceFileName = "";
      const zone = $("singleImageDropZone");
      const preview = $("singleInputPreview");
      const filename = $("singleInputFileName");
      if (zone) zone.classList.remove("has-image");
      if (preview) preview.removeAttribute("src");
      if (filename) filename.textContent = message;
    }

    function renderSingleReferenceFromOutput(imageName) {
      if (!imageName) return;
      const sourceMode = $("singleSourceMode")?.value || singleSettings().source_mode || "previous";
      if (sourceMode !== "previous") return;
      const zone = $("singleImageDropZone");
      const preview = $("singleInputPreview");
      const filename = $("singleInputFileName");
      const imageUrl = `/api/comfy/view?name=${encodeURIComponent(imageName)}&cache=${Date.now()}`;
      singleSourceImageData = "";
      singleSourceFileName = imageName;
      if (zone) zone.classList.add("has-image");
      if (preview) preview.src = imageUrl;
      if (filename) filename.textContent = `${imageName} (previous)`;
    }

    function renderSingleOutputPreview(imageName) {
      if (!imageName) return;
      if (imageName === lastSinglePreviewName) return;
      lastSinglePreviewName = imageName;
      const panel = $("singleOutputPanel");
      const image = $("singleOutputPreview");
      if (!panel || !image) return;
      panel.classList.add("has-image");
      image.src = `/api/comfy/view?name=${encodeURIComponent(imageName)}&cache=${Date.now()}`;
      if ($("singleOutputFileName")) $("singleOutputFileName").textContent = imageName;
    }

    function bindSingleEditorInputs() {
      if (!$("singleSourceMode")) return;
      $("singleSourceMode").onchange = () => {
        singleSettings().source_mode = $("singleSourceMode").value;
        debounceSaveConfig();
        if ($("singleSourceMode").value === "previous") {
          if (lastSinglePreviewName) renderSingleReferenceFromOutput(lastSinglePreviewName);
          else clearSingleReferenceImage();
        }
      };
      $("singleWidth").oninput = () => { activeModelPreset().settings.width = numericOrBlank($("singleWidth").value); debounceSaveConfig(); renderBottom(); };
      $("singleHeight").oninput = () => { activeModelPreset().settings.height = numericOrBlank($("singleHeight").value); debounceSaveConfig(); renderBottom(); };
      $("singleSteps").oninput = () => { activeModelPreset().settings.steps = numericOrBlank($("singleSteps").value); debounceSaveConfig(); };
      $("singleCfg").oninput = () => { activeModelPreset().settings.cfg = numericOrBlank($("singleCfg").value); debounceSaveConfig(); };
      $("singleDenoise").oninput = () => { activeModelPreset().settings.denoise = numericOrBlank($("singleDenoise").value); debounceSaveConfig(); };
      $("singleSeed").oninput = () => { activeModelPreset().settings.seed = numericOrBlank($("singleSeed").value); debounceSaveConfig(); };
      $("singleSeedMode").onchange = () => { activeModelPreset().settings.seed_mode = $("singleSeedMode").value; debounceSaveConfig(); };
      $("singleUpscaleScale").oninput = () => { ensureUpscale(activeModelPreset().settings).scale_by = numericOrBlank($("singleUpscaleScale").value); debounceSaveConfig(); };
      $("singleRefreshModels").onclick = refreshModels;
    }


    function fallbackSamplers() {
      return ["euler_ancestral", "euler", "dpmpp_2m", "dpmpp_2m_sde", "dpmpp_3m_sde", "ddim"];
    }

    function fallbackSchedulers() {
      return ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform", "beta"];
    }

    function modelValues(folders) {
      return [...new Set(folders.flatMap((folder) => modelLists[folder] || []))];
    }

    function renderModelSelect(id, values, current, onChange, allowBlank = false, keepMissing = true) {
      const select = $(id);
      fillSelect(select, values, current, allowBlank, keepMissing);
      const selectedValue = select.value || "";
      if (selectedValue !== (current || "")) onChange(selectedValue);
      select.onchange = () => onChange(select.value);
    }

    function renderRequiredModelSelect(id, folders, current, onChange) {
      const values = modelValues(folders);
      renderModelSelect(id, values, current, onChange, true, values.length === 0);
    }

    function renderOptionalModelSelect(id, folders, current, onChange) {
      const values = modelValues(folders);
      renderModelSelect(id, values, current, onChange, true, values.length === 0);
    }

    function fillSelect(select, values, current, allowBlank = false, keepMissing = true) {
      const unique = [...new Set(values.filter(Boolean))];
      if (current && !unique.includes(current) && keepMissing) unique.unshift(current);
      select.innerHTML = "";
      if (allowBlank) {
        const blank = document.createElement("option");
        blank.value = "";
        blank.textContent = uiText("Do not use");
        blank.selected = !current || (!keepMissing && !unique.includes(current));
        select.appendChild(blank);
      }
      unique.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        option.selected = value === current;
        select.appendChild(option);
      });
    }

    function renderLoopTab() {
      renderPresetButtons("loop");
      const preset = activeLoopPreset();
      const s = preset.settings;
      renderSelect("angleSelect", library.angles, s.angle, (value) => { s.angle = value; debounceSaveLibrary(); renderAll(); });
      renderSelect("backgroundSelect", library.backgrounds, s.background, (value) => { s.background = value; debounceSaveLibrary(); renderAll(); });
      $("useGlobalPositive").checked = s.use_global_positive ?? false;
      $("useGlobalNegative").checked = s.use_global_negative ?? false;
      $("useCustomPrompt").checked = s.use_custom_prompt ?? false;
      $("includeRandom").checked = s.include_random ?? false;
      $("expandRandomPrompts").checked = s.random_prompt_mode === "all";
      $("expandRandomPrompts").disabled = !$("includeRandom").checked;
      renderChecks("characterChecks", "characterFilter", library.characters, s.characters);
      renderChecks("outfitChecks", "outfitFilter", library.outfits, s.outfits);
      if (!Array.isArray(s.objects)) s.objects = [];
      renderChecks("objectChecks", "objectFilter", library.objects || {}, s.objects, {section: "objects", includeTextFields: true});
      renderChecks("actionChecks", "actionFilter", library.actions, s.actions, {grouped: true, section: "actions"});
    }

    function renderSelect(id, records, selected, onChange, allowBlank = false) {
      const select = $(id);
      select.innerHTML = "";
      if (allowBlank) {
        const blank = document.createElement("option");
        blank.value = "";
        blank.textContent = uiText("Do not use");
        blank.selected = !selected;
        select.appendChild(blank);
      }
      sortedRecordEntries(records, id === "angleSelect" || id === "singleAngleSelect" ? "angles" : id === "backgroundSelect" || id === "singleBackgroundSelect" ? "backgrounds" : id === "singleActionSelect" ? "actions" : "").forEach(([key, record]) => {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = label(record, key);
        option.selected = key === selected;
        select.appendChild(option);
      });
      select.onchange = () => onChange(select.value);
    }

    function sortedRecordEntries(records, section = "") {
      return Object.entries(records).sort((a, b) => {
        const ag = section ? groupSortIndex(section, recordGroupKey(section, a[1])) : 9999;
        const bg = section ? groupSortIndex(section, recordGroupKey(section, b[1])) : 9999;
        if (ag !== bg) return ag - bg;
        const ai = Number(a[1].sort_index ?? 9999);
        const bi = Number(b[1].sort_index ?? 9999);
        if (ai !== bi) return ai - bi;
        const an = a[1].number || "9999";
        const bn = b[1].number || "9999";
        const numberCompare = String(an).localeCompare(String(bn), undefined, {numeric: true});
        if (numberCompare !== 0) return numberCompare;
        const av = a[1].source_node || 999999;
        const bv = b[1].source_node || 999999;
        return av - bv || a[0].localeCompare(b[0]);
      });
    }

    function matchesFilter(record, key, filter, includeGroup = false, section = "", includeTextFields = false) {
      if (!filter) return true;
      const haystack = [
        label(record, key),
        key,
        section ? groupLabel(section, recordGroupKey(section, record), record) : "",
      ];
      if (includeTextFields) {
        haystack.push(
          record?.prompt || "",
          record?.negative_prompt || "",
          record?.random_prompt || "",
          record?.custom_prompt || "",
        );
      }
      return haystack.some((value) => String(value || "").toLowerCase().includes(filter));
    }

    function syncSelection(selectedKeys, keys, checked) {
      const keySet = new Set(keys);
      if (checked) {
        keys.forEach((key) => {
          if (!selectedKeys.includes(key)) selectedKeys.push(key);
        });
      } else {
        selectedKeys.splice(0, selectedKeys.length, ...selectedKeys.filter((item) => !keySet.has(item)));
      }
    }

    function renderCheckRow(key, record, selectedKeys, afterChange = null) {
      const row = document.createElement("label");
      row.className = "check-row";
      row.innerHTML = `<input type="checkbox" ${selectedKeys.includes(key) ? "checked" : ""}><span>${escapeHtml(label(record, key))}</span>`;
      const input = row.querySelector("input");
      input.onchange = () => {
        syncSelection(selectedKeys, [key], input.checked);
        debounceSaveLibrary();
        if (afterChange) afterChange();
        renderBottom();
      };
      return row;
    }

    function renderGroupedChecks(holder, entries, selectedKeys, section) {
      holder.classList.add("grouped");
      const groups = new Map();
      entries.forEach(([key, record]) => {
        const groupKey = recordGroupKey(section, record);
        const tag = groupLabel(section, groupKey, record);
        if (!groups.has(tag)) groups.set(tag, []);
        groups.get(tag).push([key, record]);
      });
      Array.from(groups.entries()).forEach(([groupName, items], groupIndex) => {
        const keys = items.map(([key]) => key);
        const selectedCount = keys.filter((key) => selectedKeys.includes(key)).length;
        const group = document.createElement("div");
        group.className = `check-group ${groupIndex % 2 === 0 ? "tone-a" : "tone-b"}`;
        const header = document.createElement("label");
        header.className = "check-group-header";
        header.innerHTML = `<input type="checkbox"><span>${escapeHtml(groupName)}</span><small>${selectedCount}/${keys.length}</small>`;
        const groupInput = header.querySelector("input");
        groupInput.checked = selectedCount === keys.length && keys.length > 0;
        groupInput.indeterminate = selectedCount > 0 && selectedCount < keys.length;
        groupInput.onchange = () => {
          syncSelection(selectedKeys, keys, groupInput.checked);
          debounceSaveLibrary();
          renderLoopTab();
          renderBottom();
        };
        const list = document.createElement("div");
        list.className = "check-group-list";
        items.forEach(([key, record]) => list.appendChild(renderCheckRow(key, record, selectedKeys, renderLoopTab)));
        group.appendChild(header);
        group.appendChild(list);
        holder.appendChild(group);
      });
    }

    function renderChecks(holderId, filterId, records, selectedKeys, options = {}) {
      const holder = $(holderId);
      const filter = ($(filterId).value || "").toLowerCase();
      holder.innerHTML = "";
      holder.classList.toggle("grouped", Boolean(options.grouped));
      const section = options.section || "";
      const entries = sortedRecordEntries(records, section).filter(([key, record]) => matchesFilter(record, key, filter, options.grouped, section, options.includeTextFields));
      if (options.grouped) {
        renderGroupedChecks(holder, entries, selectedKeys, section);
        return;
      }
      entries.forEach(([key, record]) => holder.appendChild(renderCheckRow(key, record, selectedKeys)));
    }

    function setVisibleSelection(section, filterId, selectedKeys, checked, grouped = false) {
      const filter = ($(filterId).value || "").toLowerCase();
      const keys = sortedRecordEntries(library[section], section)
        .filter(([key, record]) => matchesFilter(record, key, filter, grouped, section, section === "objects"))
        .map(([key]) => key);
      syncSelection(selectedKeys, keys, checked);
      debounceSaveLibrary();
      renderLoopTab();
      renderBottom();
    }

    function recordGroupKey(section, record) {
      ensureGroups(section);
      const fallback = groupEntries(section)[0]?.[0] || "default";
      const key = record?.group || record?.group_key || fallback;
      return library.groups?.[section]?.[key] ? key : fallback;
    }

    function reorderCurrentSectionGroups(sourceKey, targetKey, placeAfter, orderedKeysOverride = null) {
      const section = $("dbSection").value;
      if (isGlobalSection(section)) return;
      const groups = ensureGroups(section);
      if (!groups[sourceKey]) return;
      const currentGroupBefore = dbCurrentGroupKey;
      const currentKeyBefore = dbCurrentKey;
      const editorKeyBefore = dbEditorKey;
      const currentKeys = groupEntries(section).map(([key]) => key);
      const orderedKeys = Array.isArray(orderedKeysOverride)
        ? mergeOrderedSubset(currentKeys, orderedKeysOverride)
        : (groups[targetKey] ? reorderKeys(currentKeys, sourceKey, targetKey, placeAfter) : currentKeys);
      orderedKeys.forEach((groupKey, index) => {
        if (groups[groupKey]) groups[groupKey].sort_index = index + 1;
      });
      reindexSectionRecordsByGroups(section);
      if (groups[currentGroupBefore]) dbCurrentGroupKey = currentGroupBefore;
      if (library[section]?.[currentKeyBefore]) dbCurrentKey = currentKeyBefore;
      if (library[section]?.[editorKeyBefore]) dbEditorKey = editorKeyBefore;
      dbDirty = true;
      debounceSaveLibrary();
      renderAll();
    }

    function reorderCurrentGroupItems(sourceKey, targetKey, placeAfter, orderedKeysOverride = null) {
      const section = $("dbSection").value;
      if (isGlobalSection(section) || !dbCurrentGroupKey) return;
      const records = library[section] || {};
      if (!records[sourceKey] || recordGroupKey(section, records[sourceKey]) !== dbCurrentGroupKey) return;
      const currentKeyBefore = dbCurrentKey;
      const editorKeyBefore = dbEditorKey;
      const currentKeys = recordKeysForGroup(section, dbCurrentGroupKey);
      const orderedKeys = Array.isArray(orderedKeysOverride)
        ? mergeOrderedSubset(currentKeys, orderedKeysOverride)
        : ((records[targetKey] && recordGroupKey(section, records[targetKey]) === dbCurrentGroupKey)
          ? reorderKeys(currentKeys, sourceKey, targetKey, placeAfter)
          : currentKeys);
      reindexRecordsInGroup(section, dbCurrentGroupKey, orderedKeys);
      if (records[currentKeyBefore] && recordGroupKey(section, records[currentKeyBefore]) === dbCurrentGroupKey) {
        dbCurrentKey = currentKeyBefore;
      }
      if (records[editorKeyBefore] && recordGroupKey(section, records[editorKeyBefore]) === dbCurrentGroupKey) {
        dbEditorKey = editorKeyBefore;
      }
      dbDirty = true;
      debounceSaveLibrary();
      renderAll();
    }

    function renderDbGroups(section) {
      const groupList = $("dbGroupList");
      groupList.innerHTML = "";
      bindDbDragContainer(groupList, `db-group:${section}`, reorderCurrentSectionGroups);
      groupEntries(section).forEach(([groupKey, group]) => {
        const count = Object.values(library[section] || {}).filter((record) => recordGroupKey(section, record) === groupKey).length;
        const button = document.createElement("button");
        button.className = "db-item" + (groupKey === dbCurrentGroupKey ? " active" : "");
        setDbItemContent(button, `${groupLabel(section, groupKey)} (${count})`, true);
        bindDbDragSort(button, groupKey, reorderCurrentSectionGroups, `db-group:${section}`);
        button.onclick = () => {
          if (dbDragJustEnded) return;
          if (!applyDbEditor({rerender: false, silent: true})) return;
          dbCurrentGroupKey = groupKey;
          dbCurrentKey = "";
          renderDatabaseTab();
        };
        groupList.appendChild(button);
      });
    }

    function populateGroupSelect(section, selectedGroupKey) {
      const select = $("dbGroupSelect");
      select.innerHTML = "";
      groupEntries(section).forEach(([groupKey]) => {
        const option = document.createElement("option");
        option.value = groupKey;
        option.textContent = groupLabel(section, groupKey);
        option.selected = groupKey === selectedGroupKey;
        select.appendChild(option);
      });
    }

    function renderDatabaseTab() {
      const section = $("dbSection").value;
      const filter = ($("dbFilter").value || "").toLowerCase();
      const list = $("dbList");
      list.innerHTML = "";
      const globalSection = isGlobalSection(section);
      const editableKey = usesEditableKey(section);
      $("dbGroupTools").classList.toggle("hidden", globalSection);
      $("dbGroupWrap").classList.toggle("hidden", globalSection);
      $("dbKeyWrap").classList.toggle("hidden", !editableKey);
      $("dbKey").disabled = !editableKey;
      $("dbDisplayNameWrap").classList.toggle("span-8", editableKey);
      $("dbDisplayNameWrap").classList.toggle("span-12", !editableKey);
      $("dbDisplayName").disabled = globalSection;
      $("dbAdd").disabled = globalSection;
      if ($("dbDuplicate")) $("dbDuplicate").disabled = globalSection;
      if ($("dbDelete")) $("dbDelete").disabled = globalSection;
      $("negativeWrap").classList.toggle("hidden", globalSection);
      $("randomWrap").classList.toggle("hidden", section !== "actions");
      $("customPromptWrap").classList.toggle("hidden", section !== "actions");
      if (globalSection) {
        dbCurrentKey = section;
        dbCurrentGroupKey = "";
        const button = document.createElement("button");
        button.className = "db-item active";
        setDbItemContent(button, GLOBAL_SECTIONS[section]);
        button.onclick = () => loadDbEditor();
        list.appendChild(button);
        loadDbEditor();
        return;
      }
      ensureGroups(section);
      if (!dbCurrentGroupKey || !library.groups[section][dbCurrentGroupKey]) {
        dbCurrentGroupKey = groupEntries(section)[0]?.[0] || "";
      }
      renderDbGroups(section);
      bindDbDragContainer(list, `db-record:${section}:${dbCurrentGroupKey}`, reorderCurrentGroupItems);
      sortedRecordEntries(library[section], section).forEach(([key, record]) => {
        if (recordGroupKey(section, record) !== dbCurrentGroupKey) return;
        const text = label(record, key);
        if (filter && !text.toLowerCase().includes(filter) && !key.toLowerCase().includes(filter)) return;
        const button = document.createElement("button");
        button.className = "db-item" + (key === dbCurrentKey ? " active" : "");
        setDbItemContent(button, text, true);
        bindDbDragSort(button, key, reorderCurrentGroupItems, `db-record:${section}:${dbCurrentGroupKey}`);
        button.onclick = () => {
          if (dbDragJustEnded) return;
          if (!applyDbEditor({rerender: false, silent: true})) return;
          debounceSaveLibrary();
          dbCurrentKey = key;
          loadDbEditor();
          renderDatabaseTab();
        };
        list.appendChild(button);
      });
      if (!dbCurrentKey || !library[section][dbCurrentKey] || recordGroupKey(section, library[section][dbCurrentKey]) !== dbCurrentGroupKey) {
        dbCurrentKey = sortedRecordEntries(library[section], section).find(([_key, record]) => recordGroupKey(section, record) === dbCurrentGroupKey)?.[0] || "";
        loadDbEditor();
      }
    }

    function loadDbEditor() {
      const section = $("dbSection").value;
      dbEditorSection = section;
      dbEditorKey = dbCurrentKey;
      if (isGlobalSection(section)) {
        dbEditorKey = section;
        $("dbKey").value = section;
        $("dbDisplayName").value = GLOBAL_SECTIONS[section];
        $("dbGroupSelect").innerHTML = "";
        $("dbPrompt").value = library.defaults?.[section] || "";
        $("dbNegativePrompt").value = "";
        $("dbRandomPrompt").value = "";
        $("dbCustomPrompt").value = "";
        return;
      }
      const record = library[section][dbEditorKey] || {};
      const groupKey = recordGroupKey(section, record);
      $("dbKey").value = dbEditorKey;
      $("dbDisplayName").value = label(record, dbEditorKey);
      populateGroupSelect(section, groupKey);
      $("dbPrompt").value = record.prompt || "";
      $("dbNegativePrompt").value = record.negative_prompt || "";
      $("dbRandomPrompt").value = record.random_prompt || "";
      $("dbCustomPrompt").value = record.custom_prompt || "";
    }

    function applyDbEditor(options = {}) {
      const {rerender = true, silent = false} = options;
      const section = dbEditorSection || $("dbSection").value;
      if (isGlobalSection(section)) {
        if (!library.defaults) library.defaults = {};
        library.defaults[section] = $("dbPrompt").value;
        dbDirty = true;
        if (rerender) renderAll();
        return true;
      }
      const oldKey = dbEditorKey || dbCurrentKey;
      if (!oldKey || !library[section]) return true;
      if (!library[section][oldKey]) {
        dbEditorKey = dbCurrentKey;
        return true;
      }
      const newKey = usesEditableKey(section) ? safeKey($("dbKey").value || oldKey) : oldKey;
      if (!newKey) {
        if (!silent) alert("Key cannot be empty.");
        return false;
      }
      if (newKey !== oldKey && Object.prototype.hasOwnProperty.call(library[section], newKey)) {
        if (!silent) alert(`Key "${newKey}" already exists. Use another key.`);
        const keyInput = $("dbKey");
        if (keyInput) keyInput.value = oldKey;
        return false;
      }
      const oldRecord = library[section][oldKey] || {};
      const record = {...oldRecord};
      const previousGroupKey = recordGroupKey(section, oldRecord);
      record.name = $("dbDisplayName").value || newKey;
      record.prompt = $("dbPrompt").value;
      const selectedGroupKey = $("dbGroupSelect").value || dbCurrentGroupKey || groupEntries(section)[0]?.[0] || "default";
      const nextSortIndex = selectedGroupKey !== previousGroupKey ? nextRecordSortIndex(section, selectedGroupKey) + 1 : null;
      applyRecordOrderFields(section, record, selectedGroupKey, nextSortIndex);
      record.negative_prompt = $("dbNegativePrompt").value;
      if (section === "actions") {
        record.random_prompt = $("dbRandomPrompt").value;
        record.custom_prompt = $("dbCustomPrompt").value;
      }
      delete library[section][oldKey];
      library[section][newKey] = record;
      dbCurrentKey = newKey;
      dbEditorKey = newKey;
      dbCurrentGroupKey = selectedGroupKey;
      dbDirty = true;
      if (rerender) renderAll();
      return true;
    }

    function autoSaveDbEditor() {
      if (!applyDbEditor({rerender: false, silent: true})) return;
      debounceSaveLibrary();
    }

    function uniqueGroupKey(section, displayName) {
      ensureGroups(section);
      const groups = library.groups[section];
      const base = safeKey(displayName) || "group";
      let key = base;
      let n = 1;
      while (groups[key]) key = `${base}_${n++}`;
      return key;
    }

    function addCurrentSectionGroup() {
      const section = $("dbSection").value;
      if (isGlobalSection(section)) return;
      if (!applyDbEditor({rerender: false, silent: true})) return;
      const name = prompt("New group name", "New group");
      if (!name || !name.trim()) return;
      const groups = ensureGroups(section);
      const key = uniqueGroupKey(section, name.trim());
      const maxSort = Math.max(0, ...Object.values(groups).map((group) => Number(group.sort_index || 0)));
      groups[key] = {name: normalizeGroupLabel(name), sort_index: maxSort + 1};
      dbCurrentGroupKey = key;
      dbCurrentKey = "";
      debounceSaveLibrary();
      renderAll();
    }

    function renameCurrentSectionGroup() {
      const section = $("dbSection").value;
      if (isGlobalSection(section)) return;
      const groups = ensureGroups(section);
      const group = groups[dbCurrentGroupKey];
      if (!group) return;
      const name = prompt("Rename group", group.name || dbCurrentGroupKey);
      if (!name || !name.trim()) return;
      group.name = normalizeGroupLabel(name);
      debounceSaveLibrary();
      renderAll();
    }

    function deleteCurrentSectionGroup() {
      const section = $("dbSection").value;
      if (isGlobalSection(section)) return;
      const groups = ensureGroups(section);
      const entries = groupEntries(section);
      if (entries.length <= 1) {
        alert("At least one group must remain.");
        return;
      }
      const group = groups[dbCurrentGroupKey];
      if (!group) return;
      const targetKey = entries.find(([key]) => key !== dbCurrentGroupKey)?.[0];
      const itemCount = Object.values(library[section] || {}).filter((record) => recordGroupKey(section, record) === dbCurrentGroupKey).length;
      const targetName = groupLabel(section, targetKey);
      const message = itemCount
        ? `Delete group "${group.name}"?\n\n${itemCount} item(s) will be moved to "${targetName}".`
        : `Delete group "${group.name}"?`;
      if (!confirm(message)) return;
      Object.values(library[section] || {}).forEach((record) => {
        if (recordGroupKey(section, record) === dbCurrentGroupKey) {
          record.group = targetKey;
        }
      });
      delete groups[dbCurrentGroupKey];
      groupEntries(section).forEach(([groupKey], index) => {
        groups[groupKey].sort_index = index + 1;
      });
      reindexSectionRecordsByGroups(section);
      dbCurrentGroupKey = targetKey;
      dbCurrentKey = "";
      debounceSaveLibrary();
      renderAll();
    }

    function activeTabName() {
      return document.querySelector(".tab-btn.active")?.dataset.tab || "model";
    }

    function renderBottom() {
      const singleMode = activeTabName() === "single";
      $("totalCount").textContent = singleMode ? 1 : computeTotal();
      $("repeatCount").value = config.run.repeat_count;
      $("repeatCount").disabled = singleMode;
    }



    function normalizePromptText(value) {
      return String(value || "")
        .replace(/\r\n/g, "\n")
        .replace(/[ \t]+/g, " ")
        .replace(/\s*,\s*/g, ", ")
        .trim()
        .toLowerCase();
    }

    function promptContains(haystack, needle) {
      const target = normalizePromptText(needle);
      if (!target || target.length < 3) return false;
      return normalizePromptText(haystack).includes(target);
    }

    function latin1BytesToString(bytes) {
      let output = "";
      for (let i = 0; i < bytes.length; i += 1) output += String.fromCharCode(bytes[i]);
      try {
        return decodeURIComponent(escape(output));
      } catch {
        return output;
      }
    }

    function readPngTextChunks(buffer) {
      const bytes = new Uint8Array(buffer);
      const signature = [137, 80, 78, 71, 13, 10, 26, 10];
      if (bytes.length < 8 || signature.some((value, index) => bytes[index] !== value)) {
        return {ok: false, error: "This is not a PNG file; embedded PNG metadata cannot be read.", chunks: {}};
      }
      const decoder = new TextDecoder("utf-8", {fatal: false});
      const chunks = {};
      let offset = 8;
      while (offset + 12 <= bytes.length) {
        const length = ((bytes[offset] << 24) | (bytes[offset + 1] << 16) | (bytes[offset + 2] << 8) | bytes[offset + 3]) >>> 0;
        const type = String.fromCharCode(bytes[offset + 4], bytes[offset + 5], bytes[offset + 6], bytes[offset + 7]);
        const start = offset + 8;
        const end = start + length;
        if (end + 4 > bytes.length) break;
        const data = bytes.slice(start, end);
        if (type === "tEXt") {
          const zero = data.indexOf(0);
          if (zero > 0) {
            const key = latin1BytesToString(data.slice(0, zero));
            const value = decoder.decode(data.slice(zero + 1));
            chunks[key] = value;
          }
        } else if (type === "iTXt") {
          const parts = [];
          let last = 0;
          for (let i = 0; i < data.length && parts.length < 5; i += 1) {
            if (data[i] === 0) {
              parts.push(data.slice(last, i));
              last = i + 1;
            }
          }
          if (parts.length >= 5) {
            const key = latin1BytesToString(parts[0]);
            const compressed = parts[1]?.[0] === 1;
            chunks[key] = compressed ? "[iTXt compressed data is not supported]" : decoder.decode(data.slice(last));
          }
        }
        offset = end + 4;
      }
      return {ok: true, chunks};
    }

    function tryParseJson(value) {
      if (!value) return null;
      try {
        return JSON.parse(value);
      } catch {
        return null;
      }
    }

    function normalizeLoraName(value) {
      return String(value || "").trim().replace(/^[\s\"']+|[\s\"']+$/g, "");
    }

    function addLoraRecord(target, data = {}) {
      const name = normalizeLoraName(data.name || data.lora_name || data.model_name || data.modelName || data.filename || data.file || "");
      if (!name) return;
      const key = name.toLowerCase();
      const existing = target.find((item) => normalizeLoraName(item.name).toLowerCase() === key);
      const next = {
        name,
        strength_model: data.strength_model ?? data.model_strength ?? data.strength ?? data.weight ?? data.modelWeight ?? "",
        strength_clip: data.strength_clip ?? data.clip_strength ?? data.clipStrength ?? "",
        version: data.version || data.modelVersionName || data.model_version || data.version_name || "",
        source: data.source || ""
      };
      if (existing) {
        Object.entries(next).forEach(([field, value]) => {
          if ((existing[field] === undefined || existing[field] === null || String(existing[field]).trim() === "") && value !== undefined && value !== null && String(value).trim() !== "") {
            existing[field] = value;
          }
        });
        return;
      }
      target.push(next);
    }

    function addAnalysisRecord(target, data = {}, nameCandidates = [], fallbackName = "") {
      const name = normalizeLoraName(nameCandidates.find((value) => value !== undefined && value !== null && String(value).trim() !== "") || fallbackName);
      if (!name) return null;
      const signature = [name, data.class_type || data.classType || "", data.source || "", data.method || data.upscale_method || "", data.strength || data.weight || "", data.scale_by || data.scale || "", data.start_percent || "", data.end_percent || ""].join("|").toLowerCase();
      const existing = target.find((item) => item.signature === signature || (normalizeLoraName(item.name).toLowerCase() === name.toLowerCase() && String(item.source || "") === String(data.source || "")));
      const next = {
        ...data,
        name,
        signature
      };
      if (existing) {
        Object.entries(next).forEach(([field, value]) => {
          if (field === "signature") return;
          if ((existing[field] === undefined || existing[field] === null || String(existing[field]).trim() === "") && value !== undefined && value !== null && String(value).trim() !== "") {
            existing[field] = value;
          }
        });
        return existing;
      }
      target.push(next);
      return next;
    }

    function addEmbeddingRecord(target, data = {}) {
      return addAnalysisRecord(target, {
        strength: data.strength ?? data.weight ?? data.model_strength ?? data.strength_model ?? "",
        version: data.version || data.modelVersionName || data.model_version || data.version_name || "",
        source: data.source || data.type || data.modelType || data.resourceType || ""
      }, [data.embedding_name, data.embedding, data.name, data.model_name, data.modelName, data.filename, data.file]);
    }

    function addUpscaleRecord(target, data = {}) {
      const classType = data.class_type || data.classType || "";
      return addAnalysisRecord(target, {
        class_type: classType,
        method: data.method || data.upscale_method || data.upscaler || "",
        scale_by: data.scale_by ?? data.scale ?? data.upscale_by ?? data.factor ?? "",
        width: data.width ?? "",
        height: data.height ?? "",
        crop: data.crop ?? "",
        source: data.source || ""
      }, [data.model_name, data.upscale_model_name, data.upscale_model, data.upscaler_name, data.upscaler, data.name, data.model, data.filename, data.file], classType ? classType : "Upscale");
    }

    function addControlNetRecord(target, data = {}) {
      const classType = data.class_type || data.classType || "";
      return addAnalysisRecord(target, {
        class_type: classType,
        strength: data.strength ?? data.weight ?? data.control_net_strength ?? "",
        start_percent: data.start_percent ?? data.startPercent ?? data.start ?? "",
        end_percent: data.end_percent ?? data.endPercent ?? data.end ?? "",
        preprocessor: data.preprocessor || data.preprocessor_name || data.processor || data.detectmap || "",
        source: data.source || ""
      }, [data.control_net_name, data.controlnet_name, data.control_net, data.controlnet, data.model_name, data.modelName, data.name, data.filename, data.file], classType ? classType : "ControlNet");
    }

    function extractLoraTagsFromText(text) {
      const loras = [];
      const value = String(text || "");
      const tagPattern = /<lora:([^:>]+)(?::([^>]+))?>/gi;
      let match;
      while ((match = tagPattern.exec(value))) {
        addLoraRecord(loras, {name: match[1], strength_model: match[2] || "", source: "Prompt tag"});
      }
      return loras;
    }

    function extractEmbeddingTagsFromText(text) {
      const embeddings = [];
      const value = String(text || "");
      const angledPattern = /<embedding:([^:>]+)(?::([^>]+))?>/gi;
      let match;
      while ((match = angledPattern.exec(value))) {
        addEmbeddingRecord(embeddings, {name: match[1], strength: match[2] || "", source: "Prompt tag"});
      }
      const inlinePattern = /(?:^|[\s,(])embedding:([A-Za-z0-9_.\-\/]+)(?::([+-]?\d*\.?\d+))?/gi;
      while ((match = inlinePattern.exec(value))) {
        addEmbeddingRecord(embeddings, {name: match[1], strength: match[2] || "", source: "Prompt text"});
      }
      return embeddings;
    }

    function collectLorasFromValue(value, target, parentKey = "") {
      if (value === null || value === undefined) return;
      if (typeof value === "string") {
        extractLoraTagsFromText(value).forEach((item) => addLoraRecord(target, item));
        if (/lora/i.test(parentKey) && value.trim() && value.length < 260) addLoraRecord(target, {name: value, source: parentKey});
        return;
      }
      if (Array.isArray(value)) {
        value.forEach((item) => collectLorasFromValue(item, target, parentKey));
        return;
      }
      if (typeof value !== "object") return;

      const objectType = String(value.type || value.modelType || value.resourceType || value.kind || value.class_type || "").toLowerCase();
      const hasLoraType = objectType.includes("lora") || /lora/i.test(parentKey);
      const directName = value.lora_name || value.lora || value.name || value.model_name || value.modelName || value.filename || value.file;
      if (directName && hasLoraType) {
        addLoraRecord(target, {
          ...value,
          name: directName,
          source: value.source || value.type || value.modelType || parentKey
        });
      }
      Object.entries(value).forEach(([key, nested]) => {
        collectLorasFromValue(nested, target, key);
      });
    }

    function collectEmbeddingsFromValue(value, target, parentKey = "") {
      if (value === null || value === undefined) return;
      if (typeof value === "string") {
        extractEmbeddingTagsFromText(value).forEach((item) => addEmbeddingRecord(target, item));
        if (/(embedding|textual.?inversion)/i.test(parentKey) && value.trim() && value.length < 260) addEmbeddingRecord(target, {name: value, source: parentKey});
        return;
      }
      if (Array.isArray(value)) {
        value.forEach((item) => collectEmbeddingsFromValue(item, target, parentKey));
        return;
      }
      if (typeof value !== "object") return;

      const objectType = String(value.type || value.modelType || value.resourceType || value.kind || value.class_type || "").toLowerCase().replace(/\s+/g, "");
      const hasEmbeddingType = objectType.includes("embedding") || objectType.includes("textualinversion") || /(embedding|textual.?inversion)/i.test(parentKey);
      const directName = value.embedding_name || value.embedding || value.name || value.model_name || value.modelName || value.filename || value.file;
      if (directName && hasEmbeddingType) {
        addEmbeddingRecord(target, {
          ...value,
          name: directName,
          source: value.source || value.type || value.modelType || parentKey
        });
      }
      Object.entries(value).forEach(([key, nested]) => {
        collectEmbeddingsFromValue(nested, target, key);
      });
    }

    function collectUpscalesFromValue(value, target, parentKey = "") {
      if (value === null || value === undefined) return;
      if (typeof value === "string") {
        if (/(upscale|upscaler|hires)/i.test(parentKey) && value.trim() && value.length < 260) addUpscaleRecord(target, {name: value, source: parentKey});
        return;
      }
      if (Array.isArray(value)) {
        value.forEach((item) => collectUpscalesFromValue(item, target, parentKey));
        return;
      }
      if (typeof value !== "object") return;
      const objectType = String(value.type || value.modelType || value.resourceType || value.kind || value.class_type || "").toLowerCase();
      const hasUpscaleType = objectType.includes("upscale") || objectType.includes("upscaler") || objectType.includes("hires") || /(upscale|upscaler|hires)/i.test(parentKey);
      if (hasUpscaleType) {
        addUpscaleRecord(target, {
          ...value,
          name: value.model_name || value.upscale_model_name || value.upscale_model || value.upscaler_name || value.upscaler || value.name || value.model || value.filename || value.file || value.class_type || value.type,
          source: value.source || value.type || value.modelType || parentKey
        });
      }
      Object.entries(value).forEach(([key, nested]) => {
        collectUpscalesFromValue(nested, target, key);
      });
    }

    function collectControlNetsFromValue(value, target, parentKey = "") {
      if (value === null || value === undefined) return;
      if (typeof value === "string") {
        if (/control.?net/i.test(parentKey) && value.trim() && value.length < 260) addControlNetRecord(target, {name: value, source: parentKey});
        return;
      }
      if (Array.isArray(value)) {
        value.forEach((item) => collectControlNetsFromValue(item, target, parentKey));
        return;
      }
      if (typeof value !== "object") return;
      const objectType = String(value.type || value.modelType || value.resourceType || value.kind || value.class_type || "").toLowerCase();
      const hasControlNetType = objectType.includes("controlnet") || /control.?net/i.test(parentKey);
      if (hasControlNetType) {
        addControlNetRecord(target, {
          ...value,
          name: value.control_net_name || value.controlnet_name || value.control_net || value.controlnet || value.model_name || value.modelName || value.name || value.filename || value.file || value.class_type || value.type,
          source: value.source || value.type || value.modelType || parentKey
        });
      }
      Object.entries(value).forEach(([key, nested]) => {
        collectControlNetsFromValue(nested, target, key);
      });
    }

    function extractLorasFromPromptGraph(promptGraph) {
      const loras = [];
      if (!promptGraph || typeof promptGraph !== "object") return loras;
      Object.values(promptGraph).forEach((node) => {
        if (!node || typeof node !== "object") return;
        const classType = String(node.class_type || "");
        const inputs = node.inputs || {};
        if (/lora/i.test(classType) || Object.keys(inputs).some((key) => /lora/i.test(key))) {
          if (inputs.lora_name || inputs.lora || inputs.name) {
            addLoraRecord(loras, {
              name: inputs.lora_name || inputs.lora || inputs.name,
              strength_model: inputs.strength_model ?? inputs.model_strength ?? inputs.strength ?? inputs.weight ?? "",
              strength_clip: inputs.strength_clip ?? inputs.clip_strength ?? "",
              source: classType || "ComfyUI"
            });
          }
          collectLorasFromValue(inputs, loras, classType);
        }
      });
      return loras;
    }

    function extractEmbeddingsFromPromptGraph(promptGraph) {
      const embeddings = [];
      if (!promptGraph || typeof promptGraph !== "object") return embeddings;
      Object.values(promptGraph).forEach((node) => {
        if (!node || typeof node !== "object") return;
        const classType = String(node.class_type || "");
        const inputs = node.inputs || {};
        if (/(embedding|textual.?inversion)/i.test(classType) || Object.keys(inputs).some((key) => /(embedding|textual.?inversion)/i.test(key))) {
          addEmbeddingRecord(embeddings, {
            name: inputs.embedding_name || inputs.embedding || inputs.name || inputs.model_name,
            strength: inputs.strength ?? inputs.weight ?? "",
            source: classType || "ComfyUI"
          });
          collectEmbeddingsFromValue(inputs, embeddings, classType);
        }
      });
      return embeddings;
    }

    function extractUpscalesFromPromptGraph(promptGraph) {
      const upscales = [];
      if (!promptGraph || typeof promptGraph !== "object") return upscales;
      Object.entries(promptGraph).forEach(([nodeId, node]) => {
        if (!node || typeof node !== "object") return;
        const classType = String(node.class_type || "");
        const inputs = node.inputs || {};
        const isUpscaleNode = /(upscale|upscaler|hires)/i.test(classType) || Object.keys(inputs).some((key) => /(upscale|upscaler|scale_by|hires)/i.test(key));
        if (!isUpscaleNode) return;
        let linkedModelName = "";
        if (Array.isArray(inputs.upscale_model)) {
          const linked = nodeFromLink(promptGraph, inputs.upscale_model);
          linkedModelName = linked?.inputs?.model_name || linked?.inputs?.upscale_model_name || "";
        }
        addUpscaleRecord(upscales, {
          name: inputs.model_name || inputs.upscale_model_name || linkedModelName || inputs.upscaler_name || inputs.upscaler || inputs.name || classType,
          class_type: classType,
          method: inputs.upscale_method || inputs.method || inputs.upscaler || "",
          scale_by: inputs.scale_by ?? inputs.scale ?? inputs.upscale_by ?? inputs.factor ?? "",
          width: inputs.width ?? "",
          height: inputs.height ?? "",
          crop: inputs.crop ?? "",
          source: `ComfyUI #${nodeId}`
        });
      });
      return upscales;
    }

    function extractControlNetsFromPromptGraph(promptGraph) {
      const controlnets = [];
      if (!promptGraph || typeof promptGraph !== "object") return controlnets;
      Object.entries(promptGraph).forEach(([nodeId, node]) => {
        if (!node || typeof node !== "object") return;
        const classType = String(node.class_type || "");
        const inputs = node.inputs || {};
        const isControlNetNode = /control.?net/i.test(classType) || Object.keys(inputs).some((key) => /control.?net/i.test(key));
        if (!isControlNetNode) return;
        let linkedModelName = "";
        if (Array.isArray(inputs.control_net)) {
          const linked = nodeFromLink(promptGraph, inputs.control_net);
          linkedModelName = linked?.inputs?.control_net_name || linked?.inputs?.controlnet_name || linked?.inputs?.model_name || "";
        }
        addControlNetRecord(controlnets, {
          name: inputs.control_net_name || inputs.controlnet_name || linkedModelName || inputs.model_name || inputs.name || classType,
          class_type: classType,
          strength: inputs.strength ?? inputs.weight ?? inputs.control_net_strength ?? "",
          start_percent: inputs.start_percent ?? inputs.startPercent ?? inputs.start ?? "",
          end_percent: inputs.end_percent ?? inputs.endPercent ?? inputs.end ?? "",
          preprocessor: inputs.preprocessor || inputs.preprocessor_name || inputs.processor || "",
          source: `ComfyUI #${nodeId}`
        });
      });
      return controlnets;
    }

    function extractImageMetadataFromChunks(chunks) {
      const textChunks = chunks || {};
      const promptGraph = tryParseJson(textChunks.prompt);
      let metadata = extractComfyMetadata(promptGraph);
      if (!metadata && textChunks.parameters) metadata = parseParametersText(textChunks.parameters);

      const jsonValues = Object.values(textChunks)
        .map((value) => tryParseJson(value))
        .filter(Boolean);
      const allLoras = [];
      const allEmbeddings = [];
      const allUpscales = [];
      const allControlNets = [];
      if (metadata?.loras) metadata.loras.forEach((item) => addLoraRecord(allLoras, item));
      if (metadata?.embeddings) metadata.embeddings.forEach((item) => addEmbeddingRecord(allEmbeddings, item));
      if (metadata?.upscales) metadata.upscales.forEach((item) => addUpscaleRecord(allUpscales, item));
      if (metadata?.controlnets) metadata.controlnets.forEach((item) => addControlNetRecord(allControlNets, item));
      jsonValues.forEach((value) => {
        collectLorasFromValue(value, allLoras);
        collectEmbeddingsFromValue(value, allEmbeddings);
        collectUpscalesFromValue(value, allUpscales);
        collectControlNetsFromValue(value, allControlNets);
      });
      extractLoraTagsFromText(metadata?.positive || "").forEach((item) => addLoraRecord(allLoras, item));
      extractLoraTagsFromText(metadata?.negative || "").forEach((item) => addLoraRecord(allLoras, item));
      extractEmbeddingTagsFromText(metadata?.positive || "").forEach((item) => addEmbeddingRecord(allEmbeddings, item));
      extractEmbeddingTagsFromText(metadata?.negative || "").forEach((item) => addEmbeddingRecord(allEmbeddings, item));
      if (textChunks.parameters && !metadata) {
        extractLoraTagsFromText(textChunks.parameters).forEach((item) => addLoraRecord(allLoras, item));
        extractEmbeddingTagsFromText(textChunks.parameters).forEach((item) => addEmbeddingRecord(allEmbeddings, item));
      }
      if (!metadata && (allLoras.length || allEmbeddings.length || allUpscales.length || allControlNets.length)) {
        metadata = {source: "Metadata", positive: "", negative: ""};
      }
      if (metadata) {
        metadata.loras = allLoras;
        metadata.embeddings = allEmbeddings;
        metadata.upscales = allUpscales;
        metadata.controlnets = allControlNets;
      }
      return metadata;
    }

    function firstNodeByClass(graph, matcher) {
      if (!graph || typeof graph !== "object") return ["", null];
      return Object.entries(graph).find(([_id, node]) => node && matcher(String(node.class_type || ""))) || ["", null];
    }

    function nodeFromLink(graph, link) {
      if (!Array.isArray(link) || !link.length) return null;
      return graph?.[String(link[0])] || null;
    }

    function extractComfyMetadata(promptGraph) {
      if (!promptGraph || typeof promptGraph !== "object") return null;
      const [samplerId, sampler] = firstNodeByClass(promptGraph, (type) => type.includes("KSampler"));
      const positiveNode = nodeFromLink(promptGraph, sampler?.inputs?.positive);
      const negativeNode = nodeFromLink(promptGraph, sampler?.inputs?.negative);
      const latentNode = nodeFromLink(promptGraph, sampler?.inputs?.latent_image);
      const [_saveId, saveNode] = firstNodeByClass(promptGraph, (type) => type === "SaveImage" || type.includes("Save"));
      const [_unetId, unetNode] = firstNodeByClass(promptGraph, (type) => type === "UNETLoader");
      const [_clipId, clipNode] = firstNodeByClass(promptGraph, (type) => type === "CLIPLoader" || type === "DualCLIPLoader");
      const [_vaeId, vaeNode] = firstNodeByClass(promptGraph, (type) => type === "VAELoader");
      const clipTextNodes = Object.values(promptGraph).filter((node) => node?.class_type === "CLIPTextEncode");
      const positive = positiveNode?.inputs?.text || clipTextNodes[0]?.inputs?.text || "";
      const negative = negativeNode?.inputs?.text || clipTextNodes[1]?.inputs?.text || "";
      const loras = extractLorasFromPromptGraph(promptGraph);
      const embeddings = extractEmbeddingsFromPromptGraph(promptGraph);
      extractEmbeddingTagsFromText(positive).forEach((item) => addEmbeddingRecord(embeddings, item));
      extractEmbeddingTagsFromText(negative).forEach((item) => addEmbeddingRecord(embeddings, item));
      const upscales = extractUpscalesFromPromptGraph(promptGraph);
      const controlnets = extractControlNetsFromPromptGraph(promptGraph);
      return {
        source: "ComfyUI",
        positive,
        negative,
        sampler_id: samplerId,
        seed: sampler?.inputs?.seed,
        steps: sampler?.inputs?.steps,
        cfg: sampler?.inputs?.cfg,
        sampler_name: sampler?.inputs?.sampler_name,
        scheduler: sampler?.inputs?.scheduler,
        denoise: sampler?.inputs?.denoise,
        width: latentNode?.inputs?.width,
        height: latentNode?.inputs?.height,
        batch_size: latentNode?.inputs?.batch_size,
        filename_prefix: saveNode?.inputs?.filename_prefix,
        unet_name: unetNode?.inputs?.unet_name,
        clip_name: clipNode?.inputs?.clip_name,
        clip_type: clipNode?.inputs?.type,
        vae_name: vaeNode?.inputs?.vae_name,
        loras,
        embeddings,
        upscales,
        controlnets
      };
    }

    function parseParametersText(parameters) {
      if (!parameters) return null;
      const text = String(parameters);
      let positive = text;
      let negative = "";
      let settings = "";
      const negativeMarker = "\nNegative prompt:";
      const negativeIndex = text.indexOf(negativeMarker);
      if (negativeIndex >= 0) {
        positive = text.slice(0, negativeIndex).trim();
        const afterNegative = text.slice(negativeIndex + negativeMarker.length).trim();
        const settingsMatch = afterNegative.match(/\n(Steps:|Sampler:|CFG scale:|Seed:|Size:|Model:|Denoising strength:|Hires)/s);
        if (settingsMatch) {
          negative = afterNegative.slice(0, settingsMatch.index).trim();
          settings = settingsMatch[0].trim();
        } else {
          negative = afterNegative;
        }
      }
      const positiveSettingsMatch = positive.match(/\n(Steps:|Sampler:|CFG scale:|Seed:|Size:|Model:|Denoising strength:|Hires)/s);
      if (positiveSettingsMatch) {
        settings = positive.slice(positiveSettingsMatch.index).trim();
        positive = positive.slice(0, positiveSettingsMatch.index).trim();
      }
      const getSetting = (name) => {
        const match = settings.match(new RegExp(`${name}:\s*([^,]+)`));
        return match ? match[1].trim() : "";
      };
      const size = getSetting("Size");
      const sizeParts = size.match(/(\d+)\s*x\s*(\d+)/i);
      const upscales = [];
      const hiresUpscaler = getSetting("Hires upscaler") || getSetting("Hires upscale") || getSetting("Upscaler");
      const hiresScale = getSetting("Hires upscale") || getSetting("Hires scale");
      const denoise = getSetting("Denoising strength") || getSetting("Hires denoising strength");
      if (hiresUpscaler || hiresScale || denoise) {
        addUpscaleRecord(upscales, {
          name: hiresUpscaler || "Hires fix / Upscale",
          method: hiresUpscaler,
          scale_by: hiresScale,
          source: "Parameters"
        });
      }
      const embeddings = [];
      extractEmbeddingTagsFromText(positive).forEach((item) => addEmbeddingRecord(embeddings, item));
      extractEmbeddingTagsFromText(negative).forEach((item) => addEmbeddingRecord(embeddings, item));
      return {
        source: "Parameters",
        positive,
        negative,
        steps: getSetting("Steps"),
        sampler_name: getSetting("Sampler"),
        cfg: getSetting("CFG scale"),
        seed: getSetting("Seed"),
        width: sizeParts ? sizeParts[1] : "",
        height: sizeParts ? sizeParts[2] : "",
        denoise,
        raw_settings: settings,
        embeddings,
        upscales,
        controlnets: []
      };
    }

    function sectionLabel(section) {
      const names = {
        defaults: "Global",
        characters: "Characters",
        outfits: "Outfits",
        objects: "Objects",
        actions: "Emotion / Action",
        angles: "View",
        backgrounds: "Background",
        loras: "LoRA",
        embeddings: "Embedding",
        upscale: "Upscale",
        controlnet: "ControlNet"
      };
      return names[section] || section;
    }

    function addMatch(matches, section, key, name, field, detail = "") {
      if (!key && !name) return;
      const id = `${section}:${key}:${field}:${detail}`;
      if (matches.some((item) => item.id === id)) return;
      matches.push({id, section, key, name, field, detail});
    }

    function matchPromptLibrary(positive, negative, metadata) {
      const matches = [];
      if (!library) return matches;
      const defaults = library.defaults || {};
      if (promptContains(positive, defaults.global_positive)) addMatch(matches, "defaults", "global_positive", "Global Positive", "Prompt");
      if (promptContains(negative, defaults.global_negative)) addMatch(matches, "defaults", "global_negative", "Global Negative", "Negative Prompt");
      ["characters", "outfits", "objects", "actions", "angles", "backgrounds"].forEach((section) => {
        Object.entries(library[section] || {}).forEach(([key, record]) => {
          const displayName = label(record, key);
          if (promptContains(positive, record.prompt)) addMatch(matches, section, key, displayName, "Prompt");
          if (promptContains(negative, record.negative_prompt)) addMatch(matches, section, key, displayName, "Negative Prompt");
          if (section === "actions") {
            const randomLines = String(record.random_prompt || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
            randomLines.forEach((line, index) => {
              if (promptContains(positive, line)) addMatch(matches, section, key, displayName, "Variation prompt", `#${index + 1}`);
            });
            if (promptContains(positive, record.custom_prompt)) addMatch(matches, section, key, displayName, "Custom prompt", "");
          }
        });
      });
      const loraNames = new Set((metadata?.loras || []).map((item) => String(item.name || "").trim().toLowerCase()).filter(Boolean));
      const upscaleNames = new Set((metadata?.upscales || []).map((item) => String(item.name || "").trim().toLowerCase()).filter(Boolean));
      (config?.model_presets || []).forEach((preset) => {
        (preset.settings?.loras || []).forEach((lora, index) => {
          const name = String(lora.lora_name || "").trim();
          if (name && loraNames.has(name.toLowerCase())) addMatch(matches, "loras", `model_preset:${preset.name}:${index + 1}`, name, "LoRA");
          if (promptContains(positive, lora.positive_prompt)) addMatch(matches, "loras", `model_preset:${preset.name}:${index + 1}`, name || `LoRA ${index + 1}`, "LoRA positive prompt");
          if (promptContains(negative, lora.negative_prompt)) addMatch(matches, "loras", `model_preset:${preset.name}:${index + 1}`, name || `LoRA ${index + 1}`, "LoRA negative prompt");
        });
        const upscaleModel = String(preset.settings?.upscale?.model_name || "").trim();
        if (upscaleModel && upscaleNames.has(upscaleModel.toLowerCase())) {
          addMatch(matches, "upscale", `model_preset:${preset.name}:upscale`, upscaleModel, "Upscale model");
        }
      });
      return matches;
    }

    function hasRenderableValue(value) {
      return value !== undefined && value !== null && String(value).trim() !== "";
    }

    function renderTextBlock(title, text, badges = []) {
      const textValue = String(text || "").trim();
      if (!textValue) return "";
      const safeText = escapeHtml(textValue);
      const badgeHtml = badges.length ? `<div class="badges">${badges.map((badge) => `<span class="badge">${escapeHtml(badge)}</span>`).join("")}</div>` : "";
      return `
        <div class="metadata-section">
          <div class="metadata-title-row"><h4>${escapeHtml(title)}</h4>${badgeHtml}</div>
          <pre class="metadata-text">${safeText}</pre>
        </div>`;
    }

    function renderMetadataSection(title, bodyHtml, badges = []) {
      const content = String(bodyHtml || "").trim();
      if (!content) return "";
      const badgeHtml = badges.length ? `<div class="badges">${badges.map((badge) => `<span class="badge">${escapeHtml(badge)}</span>`).join("")}</div>` : "";
      return `
        <div class="metadata-section">
          <div class="metadata-title-row"><h4>${escapeHtml(title)}</h4>${badgeHtml}</div>
          ${content}
        </div>`;
    }

    function renderKeyValueGrid(items) {
      const visible = items.filter(([_label, value]) => hasRenderableValue(value));
      if (!visible.length) return "";
      return `<div class="kv-grid">${visible.map(([labelName, value]) => `
        <div class="kv-item"><small>${escapeHtml(labelName)}</small><span>${escapeHtml(value)}</span></div>
      `).join("")}</div>`;
    }

    function renderAnalysisList(items, emptyText, badgeLabel, detailBuilder) {
      if (!items.length) return "";
      return `<div class="lora-list">${items.map((item, index) => {
        const details = detailBuilder(item, index).filter(Boolean).join(" · ");
        return `
          <div class="lora-analysis-row">
            <div><div class="lora-analysis-name">${escapeHtml(item.name || `${badgeLabel} ${index + 1}`)}</div>${details ? `<div class="lora-analysis-detail">${escapeHtml(details)}</div>` : ""}</div>
            <span class="badge">${escapeHtml(badgeLabel)}</span>
          </div>`;
      }).join("")}</div>`;
    }

    function renderLoraList(loras) {
      return renderAnalysisList(loras, "", "LoRA", (lora) => {
        const strengths = [lora.strength_model, lora.strength_clip].filter((value) => hasRenderableValue(value)).join(" / ");
        return [
          lora.version ? `Version: ${lora.version}` : "",
          strengths ? `Strength: ${strengths}` : "",
          lora.source ? `Source: ${lora.source}` : ""
        ];
      });
    }

    function renderEmbeddingList(embeddings) {
      return renderAnalysisList(embeddings, "", "Embedding", (embedding) => [
        embedding.version ? `Version: ${embedding.version}` : "",
        embedding.strength ? `Strength: ${embedding.strength}` : "",
        embedding.source ? `Source: ${embedding.source}` : ""
      ]);
    }

    function renderUpscaleList(upscales) {
      return renderAnalysisList(upscales, "", "Upscale", (upscale) => [
        upscale.class_type ? `Node: ${upscale.class_type}` : "",
        upscale.method ? `Method: ${upscale.method}` : "",
        upscale.scale_by ? `Scale: ${upscale.scale_by}` : "",
        upscale.width || upscale.height ? `Size: ${[upscale.width, upscale.height].filter(Boolean).join(" x ")}` : "",
        upscale.crop ? `Crop: ${upscale.crop}` : "",
        upscale.source ? `Source: ${upscale.source}` : ""
      ]);
    }

    function renderControlNetList(controlnets) {
      return renderAnalysisList(controlnets, "", "ControlNet", (controlnet) => [
        controlnet.class_type ? `Node: ${controlnet.class_type}` : "",
        controlnet.strength ? `Strength: ${controlnet.strength}` : "",
        controlnet.start_percent || controlnet.end_percent ? `Range: ${controlnet.start_percent || "0"} - ${controlnet.end_percent || "1"}` : "",
        controlnet.preprocessor ? `Preprocessor: ${controlnet.preprocessor}` : "",
        controlnet.source ? `Source: ${controlnet.source}` : ""
      ]);
    }

    function renderImageAnalysis(metadata = {}, textChunks = {}, matches = [], warning = "") {
      const target = $("imageAnalysis");
      if (!target) return;
      const loras = Array.isArray(metadata?.loras) ? metadata.loras : [];
      const embeddings = Array.isArray(metadata?.embeddings) ? metadata.embeddings : [];
      const upscales = Array.isArray(metadata?.upscales) ? metadata.upscales : [];
      const controlnets = Array.isArray(metadata?.controlnets) ? metadata.controlnets : [];
      const isInitial = metadata?.source === "No image selected";
      const resourceBadges = [];
      if (metadata?.source && !isInitial) resourceBadges.push(metadata.source);
      if (loras.length) resourceBadges.push(`${loras.length} LoRA`);
      if (embeddings.length) resourceBadges.push(`${embeddings.length} Embedding`);
      if (upscales.length) resourceBadges.push(`${upscales.length} Upscale`);
      if (controlnets.length) resourceBadges.push(`${controlnets.length} ControlNet`);
      const resourceRows = [];
      if (metadata?.unet_name) resourceRows.push(["Model / UNET", metadata.unet_name]);
      if (metadata?.clip_name) resourceRows.push(["Text encoder / CLIP", metadata.clip_name]);
      if (metadata?.vae_name) resourceRows.push(["VAE", metadata.vae_name]);
      const otherRows = renderKeyValueGrid([
        ["Dimensions", metadata?.width && metadata?.height ? `${metadata.width} x ${metadata.height}` : ""],
        ["Steps", metadata?.steps],
        ["CFG", metadata?.cfg],
        ["Sampler", [metadata?.sampler_name, metadata?.scheduler].filter(Boolean).join(" / ")],
        ["Seed", metadata?.seed],
        ["Denoise", metadata?.denoise],
        ["Batch", metadata?.batch_size],
        ["Filename prefix", metadata?.filename_prefix],
        ["Text chunks", Object.keys(textChunks || {}).join(", ")]
      ]);
      const matchListHtml = (!isInitial && matches.length) ? `
        <p class="help-text">Compares the image-embedded prompts, LoRA names, and upscale model against the current <code>prompt_library.json</code> and <code>app_config.json</code>. Embedding and ControlNet data are parsed and displayed, but a database match is created only when the existing prompt-set text contains the same content. This process is read-only.</p>
        <div class="match-list">
          ${matches.map((item) => `
            <div class="match-row">
              <div class="match-section">${escapeHtml(sectionLabel(item.section))}</div>
              <div><div class="match-name">${escapeHtml(item.name)}</div><div class="match-key">${escapeHtml(item.key)}</div></div>
              <span class="badge soft">${escapeHtml([item.field, item.detail].filter(Boolean).join(" "))}</span>
            </div>
          `).join("")}
        </div>` : "";
      const blocks = [
        renderMetadataSection("Resource usage", renderKeyValueGrid(resourceRows), resourceBadges),
        loras.length ? renderMetadataSection("LoRA", renderLoraList(loras), [`${loras.length}`]) : "",
        embeddings.length ? renderMetadataSection("Embedding", renderEmbeddingList(embeddings), [`${embeddings.length}`]) : "",
        upscales.length ? renderMetadataSection("Upscale", renderUpscaleList(upscales), [`${upscales.length}`]) : "",
        controlnets.length ? renderMetadataSection("ControlNet", renderControlNetList(controlnets), [`${controlnets.length}`]) : "",
        renderTextBlock("Prompt", metadata?.positive || "", [metadata?.source && !isInitial ? metadata.source : ""].filter(Boolean)),
        renderTextBlock("Negative prompt", metadata?.negative || ""),
        renderMetadataSection("Other data", otherRows),
        matchListHtml ? renderMetadataSection("Database mapping", matchListHtml, ["Using existing JSON"]) : ""
      ].filter(Boolean).join("");
      const emptyMessage = isInitial
        ? "No image has been loaded. Generation metadata appears after an image is loaded."
        : "No displayable generation-metadata sections were found in this image.";
      target.innerHTML = `
        ${warning ? `<div class="analysis-warning">${escapeHtml(warning)}</div>` : ""}
        <div class="metadata-card">
          <h3>Generation metadata</h3>
          ${blocks || `<div class="analysis-empty">${escapeHtml(emptyMessage)}</div>`}
        </div>`;
      applyI18n(target);
      updateBottomBarSpace();
    }

    async function analyzeImageFile(file) {
      if (!file) return;
      const dropZone = $("imageDropZone");
      const preview = $("imagePreview");
      const fileName = $("imageFileName");
      const target = $("imageAnalysis");
      if (dropZone && preview) {
        dropZone.classList.add("has-image");
        preview.src = URL.createObjectURL(file);
        fileName.textContent = `${file.name} · ${Math.round(file.size / 1024)} KB`;
      }
      if (target) { target.innerHTML = '<div class="analysis-empty">Parsing image metadata...</div>'; applyI18n(target); }
      try {
        const buffer = await file.arrayBuffer();
        const png = readPngTextChunks(buffer);
        let metadata = null;
        let warning = "";
        if (png.ok) {
          metadata = extractImageMetadataFromChunks(png.chunks);
          if (!metadata) warning = Object.keys(png.chunks).length ? "Image text chunks were read, but no recognizable ComfyUI prompt or parameter format was found." : "This PNG does not contain recognizable AI-generation metadata text chunks.";
        } else {
          warning = png.error;
          metadata = null;
        }
        if (!metadata) {
          renderImageAnalysis({source: "Unknown", positive: "", negative: "", loras: [], embeddings: [], upscales: [], controlnets: []}, png.chunks || {}, [], warning);
          return;
        }
        const matches = matchPromptLibrary(metadata.positive || "", metadata.negative || "", metadata);
        renderImageAnalysis(metadata, png.chunks || {}, matches, warning);
      } catch (err) {
        if (target) { target.innerHTML = `<div class="analysis-warning">Parse failed:${escapeHtml(err.message || String(err))}</div>`; applyI18n(target); }
      }
    }

    function bindImageAnalyzeInputs() {
      const dropZone = $("imageDropZone");
      const input = $("imageFileInput");
      if (!dropZone || !input) return;
      renderImageAnalysis({source: "No image selected", positive: "", negative: "", loras: [], embeddings: [], upscales: [], controlnets: []}, {}, [], "");
      input.onchange = () => analyzeImageFile(input.files?.[0]);
      ["dragenter", "dragover"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
          event.preventDefault();
          event.stopPropagation();
          dropZone.classList.add("drag-over");
        });
      });
      ["dragleave", "dragend", "drop"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
          event.preventDefault();
          event.stopPropagation();
          if (eventName !== "drop") dropZone.classList.remove("drag-over");
        });
      });
      dropZone.addEventListener("drop", (event) => {
        dropZone.classList.remove("drag-over");
        const file = Array.from(event.dataTransfer?.files || []).find((item) => item.type.startsWith("image/"));
        if (file) analyzeImageFile(file);
      });
    }

    function renderAll() {
      renderModelTab();
      renderLoopTab();
      renderDatabaseTab();
      renderSingleTab();
      renderBottom();
      applyI18n();
      updateBottomBarSpace();
    }

    function updateBottomBarSpace() {
      const bottomBar = $("bottomBar");
      if (!bottomBar) return;
      const height = Math.ceil(bottomBar.getBoundingClientRect().height);
      document.documentElement.style.setProperty("--bottom-bar-height", `${height}px`);
    }

    function bindLayoutObservers() {
      updateBottomBarSpace();
      const bottomBar = $("bottomBar");
      if (!bottomBar) return;
      if ("ResizeObserver" in window) {
        const observer = new ResizeObserver(updateBottomBarSpace);
        observer.observe(bottomBar);
      }
      window.addEventListener("resize", updateBottomBarSpace);
      window.addEventListener("orientationchange", updateBottomBarSpace);
    }

    function bindInputs() {
      document.querySelectorAll(".tab-btn").forEach((button) => {
        button.onclick = () => {
          const previousTab = document.querySelector(".tab-btn.active")?.dataset.tab || "";
          const nextTab = button.dataset.tab || "";
          const touchesSingle = previousTab === "single" || nextTab === "single";
          if (touchesSingle) {
            clearTimeout(configSaveTimer);
            clearTimeout(librarySaveTimer);
            saveConfig();
            saveLibraryData();
          }
          document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
          document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
          button.classList.add("active");
          $(`tab-${nextTab}`).classList.add("active");
          if (touchesSingle) {
            renderAll();
          } else {
            renderBottom();
            updateBottomBarSpace();
          }
        };
      });
      bindImageAnalyzeInputs();
      bindSingleImageInputs();
      bindSingleEditorInputs();

      const modelFields = {
        width: (v) => activeModelPreset().settings.width = numericOrBlank(v),
        height: (v) => activeModelPreset().settings.height = numericOrBlank(v),
        steps: (v) => activeModelPreset().settings.steps = numericOrBlank(v),
        cfg: (v) => activeModelPreset().settings.cfg = numericOrBlank(v),
        denoise: (v) => activeModelPreset().settings.denoise = numericOrBlank(v),
        seed: (v) => activeModelPreset().settings.seed = numericOrBlank(v),
        seedMode: (v) => activeModelPreset().settings.seed_mode = v
      };
      Object.entries(modelFields).forEach(([id, setter]) => {
        $(id).oninput = () => { setter($(id).value); debounceSaveConfig(); renderPresetButtons("model"); renderBottom(); };
        $(id).onchange = $(id).oninput;
      });
      $("upscaleScale").oninput = () => { ensureUpscale(activeModelPreset().settings).scale_by = numericOrBlank($("upscaleScale").value); debounceSaveConfig(); };
      $("renameModelPreset").onclick = () => {
        const preset = activeModelPreset();
        const nextName = prompt(uiText("Rename preset"), preset.name);
        if (nextName && nextName.trim()) {
          preset.name = nextName.trim();
          debounceSaveConfig();
          renderPresetButtons("model");
        }
      };

      $("renameLoopPreset").onclick = () => {
        const index = config.active_loop_preset;
        const nextName = prompt(uiText("Rename preset"), loopPresetName(index));
        if (nextName && nextName.trim()) {
          activeLoopPreset().name = nextName.trim();
          debounceSaveLibrary();
          renderPresetButtons("loop");
        }
      };
      $("useGlobalPositive").onchange = () => { activeLoopPreset().settings.use_global_positive = $("useGlobalPositive").checked; debounceSaveLibrary(); };
      $("useGlobalNegative").onchange = () => { activeLoopPreset().settings.use_global_negative = $("useGlobalNegative").checked; debounceSaveLibrary(); };
      $("useCustomPrompt").onchange = () => { activeLoopPreset().settings.use_custom_prompt = $("useCustomPrompt").checked; debounceSaveLibrary(); };
      $("includeRandom").onchange = () => {
        activeLoopPreset().settings.include_random = $("includeRandom").checked;
        debounceSaveLibrary();
        renderLoopTab();
        renderBottom();
      };
      $("expandRandomPrompts").onchange = () => {
        activeLoopPreset().settings.random_prompt_mode = $("expandRandomPrompts").checked ? "all" : "random";
        debounceSaveLibrary();
        renderBottom();
      };

      const selectionButtons = [
        ["selectAllCharacters", "characters", "characterFilter", "characters", true, false],
        ["clearAllCharacters", "characters", "characterFilter", "characters", false, false],
        ["selectAllOutfits", "outfits", "outfitFilter", "outfits", true, false],
        ["clearAllOutfits", "outfits", "outfitFilter", "outfits", false, false],
        ["selectAllObjects", "objects", "objectFilter", "objects", true, false],
        ["clearAllObjects", "objects", "objectFilter", "objects", false, false],
        ["selectAllActions", "actions", "actionFilter", "actions", true, true],
        ["clearAllActions", "actions", "actionFilter", "actions", false, true],
      ];
      selectionButtons.forEach(([buttonId, section, filterId, settingKey, checked, grouped]) => {
        $(buttonId).onclick = () => setVisibleSelection(
          section,
          filterId,
          activeLoopPreset().settings[settingKey],
          checked,
          grouped,
        );
      });

      ["characterFilter", "outfitFilter", "objectFilter", "actionFilter"].forEach((id) => {
        const input = $(id);
        if (!input) return;
        input.oninput = renderLoopTab;
        input.addEventListener("input", renderLoopTab);
      });
      $("dbSection").onchange = () => {
        applyDbEditor({rerender: false, silent: true});
        debounceSaveLibrary();
        dbCurrentKey = "";
        dbCurrentGroupKey = "";
        dbEditorKey = "";
        renderDatabaseTab();
      };
      $("dbFilter").oninput = renderDatabaseTab;
      $("dbAddGroup").onclick = addCurrentSectionGroup;
      $("dbRenameGroup").onclick = renameCurrentSectionGroup;
      $("dbDeleteGroup").onclick = deleteCurrentSectionGroup;
      $("dbGroupSelect").onchange = () => {
        if (!applyDbEditor({rerender: false})) return;
        renderDatabaseTab();
        debounceSaveLibrary();
      };
      ["dbKey", "dbDisplayName", "dbPrompt", "dbNegativePrompt", "dbRandomPrompt", "dbCustomPrompt"].forEach((id) => {
        const field = $(id);
        if (!field) return;
        field.oninput = autoSaveDbEditor;
        field.onchange = autoSaveDbEditor;
      });
      $("dbAdd").onclick = async () => {
        if (!applyDbEditor({rerender: false, silent: true})) return;
        const section = $("dbSection").value;
        if (isGlobalSection(section)) return;
        const groupKey = dbCurrentGroupKey || groupEntries(section)[0]?.[0] || "default";
        let key = "new_item";
        let n = 1;
        while (library[section][key]) key = `new_item_${n++}`;
        library[section][key] = {
          name: "New item",
          group: groupKey,
          prompt: "",
          negative_prompt: ""
        };
        applyRecordOrderFields(section, library[section][key], groupKey, nextRecordSortIndex(section, groupKey) + 1);
        if (section === "actions") {
          library[section][key].random_prompt = "";
          library[section][key].custom_prompt = "";
        }
        dbCurrentKey = key;
        dbCurrentGroupKey = groupKey;
        dbDirty = true;
        renderAll();
        loadDbEditor();
        await saveLibrary({applyCurrent: false, message: uiText("New item saved")});
      };
      // The data editor now autosaves; copy, delete, and manual-save buttons have been removed.
      $("refreshModels").onclick = refreshModels;

      $("repeatCount").oninput = () => { config.run.repeat_count = Number($("repeatCount").value); debounceSaveConfig(); renderBottom(); };
      $("startBtn").onclick = startRun;
      $("stopBtn").onclick = stopRun;
    }

    async function saveLibrary(options = {}) {
      const {applyCurrent = true, message = uiText("Changes saved")} = options;
      if (applyCurrent && !applyDbEditor({rerender: false})) return;
      await saveLibraryData();
      dbDirty = false;
      renderAll();
      setMessage(message);
    }

    async function buildPrompts() {
      await saveConfig();
      await saveLibraryData();
      const result = await api("/api/build", {method: "POST"});
      if (result.config) {
        config = result.config;
        renderAll();
      }
      let message = `Generated prompts.json with ${result.count} image(s)`;
      if (result.seed_info?.mode === "random" && result.seed_info.updated) {
        message += `, random seed updated to ${result.seed_info.seed}`;
      }
      setMessage(message);
      await updateRunStatus();
    }

    async function dryRun() {
      await saveConfig();
      await saveLibraryData();
      const result = await api("/api/build", {method: "POST"});
      if (result.config) {
        config = result.config;
        renderAll();
      }
      const preview = result.preview.map((item) => {
        const objectPart = item.object ? ` / ${item.object}` : "";
        return `${String(item.index).padStart(5, "0")} ${item.character} / ${item.outfit}${objectPart} / ${item.action}`;
      }).join("\n");
      $("logs").textContent = preview || uiText("No items");
    }

    async function startRun() {
      const activeTab = document.querySelector(".tab-btn.active")?.dataset.tab || "model";
      if (activeTab === "single") {
        await startSingleRun();
        return;
      }
      try {
        $("startBtn").disabled = true;
        const modelOverride = currentModelOverrideForRun();
        await saveConfig({raise: true});
        await saveLibraryData();
        const result = await api("/api/run/start", {
          method: "POST",
          body: JSON.stringify({model_override: modelOverride})
        });
        if (result.config) {
          config = result.config;
          renderAll();
        }
        setMessage(result.message);
      } catch (err) {
        setMessage(err.message || uiText("Failed to start run"));
      } finally {
        await updateRunStatus();
      }
    }

    async function startSingleRun() {
      try {
        $("startBtn").disabled = true;
        syncModelInputsFromDom();
        await saveConfig({raise: true});
        await saveLibraryData();
        const single = singleSettings();
        if ((single.source_mode || "previous") === "previous") {
          if (lastSinglePreviewName) renderSingleReferenceFromOutput(lastSinglePreviewName);
          else clearSingleReferenceImage();
        }
        const modelOverride = currentModelOverrideForRun();
        const result = await api("/api/single/run/start", {
          method: "POST",
          body: JSON.stringify({
            source_mode: single.source_mode || "previous",
            model_override: modelOverride
          })
        });
        if (result.config) {
          config = result.config;
          renderAll();
        }
        setMessage(result.message);
      } catch (err) {
        setMessage(err.message || uiText("Failed to run single-image generation"));
      } finally {
        await updateRunStatus();
      }
    }

    async function stopRun() {
      try {
        const result = await api("/api/run/stop", {method: "POST"});
        setMessage(result.message);
      } catch (err) {
        setMessage(err.message || uiText("Failed to stop"));
      } finally {
        await updateRunStatus();
      }
    }

    async function refreshModels() {
      try {
        syncModelInputsFromDom();
        const result = await api("/api/comfy/models");
        modelLists = result.models || {};
        renderModelTab();
        renderSingleTab();
        applyI18n(document.body);
        setMessage(uiText("Model list refreshed"));
      } catch (err) {
        setMessage(uiText("Failed to load the model list. Start ComfyUI first."));
      }
    }

    async function updateComfyStatus() {
      try {
        const result = await api("/api/comfy/status");
        $("comfyDot").classList.toggle("ok", !!result.connected);
        $("comfyText").textContent = result.connected ? uiText("ComfyUI connected") : uiText("Start ComfyUI first");
      } catch {
        $("comfyDot").classList.remove("ok");
        $("comfyText").textContent = uiText("Start ComfyUI first");
      }
    }

    async function updateRunStatus() {
      const result = await api("/api/run/status");
      $("runProgress").textContent = `${result.current} / ${result.total}`;
      const seconds = Number(result.average_duration || result.last_duration || 0);
      $("secondsPerImage").textContent = seconds > 0 ? `${seconds.toFixed(1)}${uiText("sec/image")}` : "--";
      $("runStatusText").textContent = result.status_message ? uiRuntimeText(result.status_message) : (result.running ? uiText("Running") : uiText("Idle"));
      $("startBtn").disabled = !!result.running;
      $("stopBtn").disabled = !result.running;
      $("logs").textContent = (result.logs || []).map(uiRuntimeText).join("\n");
      if (!result.running && Array.isArray(result.last_outputs) && result.last_outputs.length) renderSingleOutputPreview(result.last_outputs[0]);
      updateBottomBarSpace();
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
    }

    function safeKey(value) {
      return String(value || "").trim().replace(/\s+/g, "_").replace(/[^A-Za-z0-9_.-]/g, "_").replace(/_+/g, "_").replace(/^_+|_+$/g, "");
    }

    async function init() {
      bindUiChromeControls();
      bindLayoutObservers();
      bindInputs();
      const result = await api("/api/state");
      config = result.config;
      library = result.library;
      renderAll();
      await updateComfyStatus();
      await refreshModels();
      await updateRunStatus();
      setInterval(updateComfyStatus, 5000);
      setInterval(updateRunStatus, 2000);
    }

    init().catch((err) => {
      document.body.innerHTML = `<pre>${escapeHtml(err.stack || err.message)}</pre>`;
    });
