#!/usr/bin/env python3
"""
i18n.py — internationalization for filament_to_bambuddy.

Mirrors Bambuddy's own backend/app/i18n module: a flat dict of translations
per language, looked up by a dot-separated key with str.format()-style
interpolation ("{name}"), falling back to English when a language or key is
missing. Kept as a single small module (no build step, no npm i18n
framework) to match this app's plain Flask + vanilla-JS architecture — the
same dicts are used to translate both the Jinja-rendered page and the
in-browser JS (see templates/index.html, which embeds the active language's
dict as `window.I18N` and re-implements the same key-lookup + interpolation
in JS).

Copyright (C) 2026 Victor Manuel (hibikipr)
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from typing import Any

EN = {
    "app": {
        "title": "Filament → Bambuddy",
    },
    "ptr": {
        "pull": "Pull to refresh",
        "release": "Release to refresh",
        "refreshing": "Refreshing…",
    },
    "health": {
        "checking": "Checking Bambuddy…",
        "connected": "Connected to {bambuddy}",
        "permission_issue": "Permission issue",
        "not_reachable": "Bambuddy not reachable",
        "using": "using {bambuddy}",
        "server_error": "Server error",
    },
    "scan": {
        "refresh_db": "⟳ Refresh DB",
        "refreshing_db": "Refreshing database…",
        "refresh_updated": "Updated: {barcodes} OFD barcodes, {brands} brands.",
        "refresh_updated_smdb": " +{count} SpoolmanDB-Community barcodes.",
        "refresh_failed": "Refresh failed",
        "clear_cache": "🗑 Clear remembered lookups",
        "clear_confirm": "Forget all remembered barcode lookups? (The Open Filament Database is unaffected.)",
        "cleared": "Cleared {count} remembered lookup",
        "cleared_plural": "Cleared {count} remembered lookups",
        "clear_failed": "Clear failed",
        "scan_button": "📷 Scan barcode",
        "stop_camera": "Stop camera",
        "manual_label": "…or enter the barcode/SKU number",
        "manual_placeholder": "e.g. 6940082300018",
        "lookup_button": "Look up",
        "or_separator": "— or —",
        "ocr_button": "📸 Photograph the label to read its text",
        "camera_needs_https": "Camera needs https:// (or localhost). Type the barcode below instead.",
        "scanner_lib_failed": "Scanner library failed to load",
        "align_barcode": "Align the barcode within the frame…",
        "camera_error": "Camera error: {error}",
        "looking_up": "Looking up {barcode}…",
        "lookup_failed": "Lookup failed",
        "invalid_barcode": (
            "Enter a valid UPC-A/EAN-8/EAN-13 barcode, or a manufacturer "
            "SKU/article number (3+ characters)."
        ),
    },
    "form": {
        "title": "Filament details",
        "forget": "🗑 Forget",
        "paste_title_label": "Paste product title to auto-fill (optional)",
        "paste_title_placeholder": "e.g. SUNLU PLA+ 1.75mm Black 1KG",
        "fill_button": "✨ Fill",
        "fill_hint": "Find the listing, copy its name, tap Fill.",
        "search_link": "🔍 Search the web for this code",
        "material": "Material *",
        "brand": "Brand",
        "subtype": "Subtype / finish",
        "color_name": "Colour name",
        "color": "Colour",
        "net_weight": "Net weight (g)",
        "quantity": "Quantity",
        "storage_location": "Storage location",
        "category": "Category",
        "optional_placeholder": "optional",
        "nozzle_min": "Nozzle min °C",
        "nozzle_max": "Nozzle max °C",
        "cost_per_kg": "Cost /kg",
        "note": "Note",
        "submit": "＋ Add to Bambuddy inventory",
        "forgotten": "Forgotten — it won't auto-fill next time",
        "forget_failed": "Failed",
        "manual_entry": "entered manually",
        "also_matches": "Also matches: {codes}",
        "refill_suffix": " (refill)",
        "barcode_label": "Barcode:",
        "parse_failed": "Couldn't parse that title",
        "parse_request_failed": "Parse failed",
    },
    "badge": {
        "cache": "remembered",
        "ofd": "Open Filament Database",
        "smdb": "SpoolmanDB-Community",
        "label": "read from label photo — check carefully",
        "amazon": "Amazon code — enter below (I'll remember it)",
        "none": "not in database — enter below (I'll remember it)",
    },
    "ocr": {
        "loading_recognizer": "Loading text recognizer (first time only)…",
        "reading_label": "Reading label…",
        "reading_label_rotated": "Reading label (rotated {deg}°)… {percent}%",
        "no_text_found": "No text found — try a clearer, closer photo.",
        "couldnt_read": (
            "Couldn't read the label clearly. Try a closer, flatter, well-lit "
            "photo of the spec text — or fill in the details below."
        ),
        "failed": "OCR failed: {error}",
    },
    "submit": {
        "material_required": "Material is required",
        "added": "Added {count} spool",
        "added_plural": "Added {count} spools",
        "failed": "Failed",
        "request_failed": "Request failed",
    },
}

DE = {
    "app": {
        "title": "Filament → Bambuddy",
    },
    "ptr": {
        "pull": "Zum Aktualisieren ziehen",
        "release": "Loslassen zum Aktualisieren",
        "refreshing": "Wird aktualisiert…",
    },
    "health": {
        "checking": "Bambuddy wird geprüft…",
        "connected": "Verbunden mit {bambuddy}",
        "permission_issue": "Berechtigungsproblem",
        "not_reachable": "Bambuddy nicht erreichbar",
        "using": "verwendet {bambuddy}",
        "server_error": "Serverfehler",
    },
    "scan": {
        "refresh_db": "⟳ Datenbank aktualisieren",
        "refreshing_db": "Datenbank wird aktualisiert…",
        "refresh_updated": "Aktualisiert: {barcodes} OFD-Barcodes, {brands} Marken.",
        "refresh_updated_smdb": " +{count} SpoolmanDB-Community-Barcodes.",
        "refresh_failed": "Aktualisierung fehlgeschlagen",
        "clear_cache": "🗑 Gespeicherte Suchen löschen",
        "clear_confirm": "Alle gespeicherten Barcode-Suchen vergessen? (Die Open Filament Database ist nicht betroffen.)",
        "cleared": "{count} gespeicherte Suche gelöscht",
        "cleared_plural": "{count} gespeicherte Suchen gelöscht",
        "clear_failed": "Löschen fehlgeschlagen",
        "scan_button": "📷 Barcode scannen",
        "stop_camera": "Kamera stoppen",
        "manual_label": "…oder Barcode-/Artikelnummer eingeben",
        "manual_placeholder": "z. B. 6940082300018",
        "lookup_button": "Suchen",
        "or_separator": "— oder —",
        "ocr_button": "📸 Etikett fotografieren, um den Text zu lesen",
        "camera_needs_https": "Kamera benötigt https:// (oder localhost). Barcode stattdessen unten eingeben.",
        "scanner_lib_failed": "Scanner-Bibliothek konnte nicht geladen werden",
        "align_barcode": "Barcode im Rahmen ausrichten…",
        "camera_error": "Kamerafehler: {error}",
        "looking_up": "{barcode} wird gesucht…",
        "lookup_failed": "Suche fehlgeschlagen",
        "invalid_barcode": (
            "Gib einen gültigen UPC-A/EAN-8/EAN-13-Barcode oder eine "
            "Hersteller-Artikelnummer ein (mind. 3 Zeichen)."
        ),
    },
    "form": {
        "title": "Filament-Details",
        "forget": "🗑 Vergessen",
        "paste_title_label": "Produkttitel zum automatischen Ausfüllen einfügen (optional)",
        "paste_title_placeholder": "z. B. SUNLU PLA+ 1.75mm Schwarz 1KG",
        "fill_button": "✨ Ausfüllen",
        "fill_hint": "Angebot suchen, Namen kopieren, auf Ausfüllen tippen.",
        "search_link": "🔍 Im Web nach diesem Code suchen",
        "material": "Material *",
        "brand": "Marke",
        "subtype": "Subtyp / Oberfläche",
        "color_name": "Farbname",
        "color": "Farbe",
        "net_weight": "Nettogewicht (g)",
        "quantity": "Menge",
        "storage_location": "Lagerort",
        "category": "Kategorie",
        "optional_placeholder": "optional",
        "nozzle_min": "Düse min °C",
        "nozzle_max": "Düse max °C",
        "cost_per_kg": "Kosten /kg",
        "note": "Notiz",
        "submit": "＋ Zu Bambuddy-Inventar hinzufügen",
        "forgotten": "Vergessen — wird beim nächsten Mal nicht automatisch ausgefüllt",
        "forget_failed": "Fehlgeschlagen",
        "manual_entry": "manuell eingegeben",
        "also_matches": "Passt auch zu: {codes}",
        "refill_suffix": " (Nachfüllung)",
        "barcode_label": "Barcode:",
        "parse_failed": "Titel konnte nicht verarbeitet werden",
        "parse_request_failed": "Verarbeitung fehlgeschlagen",
    },
    "badge": {
        "cache": "gespeichert",
        "ofd": "Open Filament Database",
        "smdb": "SpoolmanDB-Community",
        "label": "vom Etikettfoto gelesen — bitte prüfen",
        "amazon": "Amazon-Code — unten eingeben (wird gespeichert)",
        "none": "nicht in der Datenbank — unten eingeben (wird gespeichert)",
    },
    "ocr": {
        "loading_recognizer": "Texterkennung wird geladen (nur beim ersten Mal)…",
        "reading_label": "Etikett wird gelesen…",
        "reading_label_rotated": "Etikett wird gelesen (gedreht {deg}°)… {percent}%",
        "no_text_found": "Kein Text gefunden — bitte ein schärferes, näheres Foto versuchen.",
        "couldnt_read": (
            "Etikett konnte nicht klar gelesen werden. Versuche ein näheres, "
            "flacheres, gut beleuchtetes Foto des Beschriftungstextes — oder "
            "fülle die Details unten aus."
        ),
        "failed": "OCR fehlgeschlagen: {error}",
    },
    "submit": {
        "material_required": "Material ist erforderlich",
        "added": "{count} Spule hinzugefügt",
        "added_plural": "{count} Spulen hinzugefügt",
        "failed": "Fehlgeschlagen",
        "request_failed": "Anfrage fehlgeschlagen",
    },
}

ES = {
    "app": {"title": "Filament → Bambuddy"},
    "ptr": {
        "pull": "Desliza para actualizar",
        "release": "Suelta para actualizar",
        "refreshing": "Actualizando…",
    },
    "health": {
        "checking": "Comprobando Bambuddy…",
        "connected": "Conectado a {bambuddy}",
        "permission_issue": "Problema de permisos",
        "not_reachable": "Bambuddy no accesible",
        "using": "usando {bambuddy}",
        "server_error": "Error del servidor",
    },
    "scan": {
        "refresh_db": "⟳ Actualizar BD",
        "refreshing_db": "Actualizando base de datos…",
        "refresh_updated": "Actualizado: {barcodes} códigos OFD, {brands} marcas.",
        "refresh_updated_smdb": " +{count} códigos de SpoolmanDB-Community.",
        "refresh_failed": "Error al actualizar",
        "clear_cache": "🗑 Borrar búsquedas recordadas",
        "clear_confirm": "¿Olvidar todas las búsquedas de códigos recordadas? (La Open Filament Database no se ve afectada.)",
        "cleared": "Se borró {count} búsqueda recordada",
        "cleared_plural": "Se borraron {count} búsquedas recordadas",
        "clear_failed": "Error al borrar",
        "scan_button": "📷 Escanear código",
        "stop_camera": "Detener cámara",
        "manual_label": "…o introduce el código/SKU",
        "manual_placeholder": "p. ej. 6940082300018",
        "lookup_button": "Buscar",
        "or_separator": "— o —",
        "ocr_button": "📸 Fotografiar la etiqueta para leer el texto",
        "camera_needs_https": "La cámara necesita https:// (o localhost). Escribe el código abajo.",
        "scanner_lib_failed": "No se pudo cargar la librería del escáner",
        "align_barcode": "Alinea el código dentro del marco…",
        "camera_error": "Error de cámara: {error}",
        "looking_up": "Buscando {barcode}…",
        "lookup_failed": "Error en la búsqueda",
        "invalid_barcode": (
            "Introduce un código UPC-A/EAN-8/EAN-13 válido, o un número de "
            "referencia/SKU del fabricante (3+ caracteres)."
        ),
    },
    "form": {
        "title": "Detalles del filamento",
        "forget": "🗑 Olvidar",
        "paste_title_label": "Pega el título del producto para autocompletar (opcional)",
        "paste_title_placeholder": "p. ej. SUNLU PLA+ 1.75mm Negro 1KG",
        "fill_button": "✨ Rellenar",
        "fill_hint": "Busca el anuncio, copia su nombre, pulsa Rellenar.",
        "search_link": "🔍 Buscar este código en la web",
        "material": "Material *",
        "brand": "Marca",
        "subtype": "Subtipo / acabado",
        "color_name": "Nombre del color",
        "color": "Color",
        "net_weight": "Peso neto (g)",
        "quantity": "Cantidad",
        "storage_location": "Ubicación de almacenamiento",
        "category": "Categoría",
        "optional_placeholder": "opcional",
        "nozzle_min": "Boquilla mín °C",
        "nozzle_max": "Boquilla máx °C",
        "cost_per_kg": "Costo /kg",
        "note": "Nota",
        "submit": "＋ Añadir al inventario de Bambuddy",
        "forgotten": "Olvidado — no se autocompletará la próxima vez",
        "forget_failed": "Error",
        "manual_entry": "introducido manualmente",
        "also_matches": "También coincide con: {codes}",
        "refill_suffix": " (recarga)",
        "barcode_label": "Código:",
        "parse_failed": "No se pudo analizar ese título",
        "parse_request_failed": "Error al analizar",
    },
    "badge": {
        "cache": "recordado",
        "ofd": "Open Filament Database",
        "smdb": "SpoolmanDB-Community",
        "label": "leído de la foto de la etiqueta — verifica con cuidado",
        "amazon": "Código de Amazon — introdúcelo abajo (lo recordaré)",
        "none": "no está en la base de datos — introdúcelo abajo (lo recordaré)",
    },
    "ocr": {
        "loading_recognizer": "Cargando reconocedor de texto (solo la primera vez)…",
        "reading_label": "Leyendo etiqueta…",
        "reading_label_rotated": "Leyendo etiqueta (girada {deg}°)… {percent}%",
        "no_text_found": "No se encontró texto — prueba con una foto más clara y cercana.",
        "couldnt_read": (
            "No se pudo leer la etiqueta claramente. Prueba con una foto más "
            "cercana, plana y bien iluminada del texto — o completa los "
            "detalles abajo."
        ),
        "failed": "Error de OCR: {error}",
    },
    "submit": {
        "material_required": "El material es obligatorio",
        "added": "Se añadió {count} bobina",
        "added_plural": "Se añadieron {count} bobinas",
        "failed": "Error",
        "request_failed": "Error en la solicitud",
    },
}

FR = {
    "app": {"title": "Filament → Bambuddy"},
    "ptr": {
        "pull": "Tirer pour actualiser",
        "release": "Relâcher pour actualiser",
        "refreshing": "Actualisation…",
    },
    "health": {
        "checking": "Vérification de Bambuddy…",
        "connected": "Connecté à {bambuddy}",
        "permission_issue": "Problème de permission",
        "not_reachable": "Bambuddy inaccessible",
        "using": "via {bambuddy}",
        "server_error": "Erreur serveur",
    },
    "scan": {
        "refresh_db": "⟳ Actualiser la BD",
        "refreshing_db": "Actualisation de la base de données…",
        "refresh_updated": "Mis à jour : {barcodes} codes OFD, {brands} marques.",
        "refresh_updated_smdb": " +{count} codes SpoolmanDB-Community.",
        "refresh_failed": "Échec de l'actualisation",
        "clear_cache": "🗑 Effacer les recherches mémorisées",
        "clear_confirm": "Oublier toutes les recherches de codes mémorisées ? (La Open Filament Database n'est pas affectée.)",
        "cleared": "{count} recherche mémorisée effacée",
        "cleared_plural": "{count} recherches mémorisées effacées",
        "clear_failed": "Échec de l'effacement",
        "scan_button": "📷 Scanner un code",
        "stop_camera": "Arrêter la caméra",
        "manual_label": "…ou saisissez le code-barres/SKU",
        "manual_placeholder": "ex. 6940082300018",
        "lookup_button": "Rechercher",
        "or_separator": "— ou —",
        "ocr_button": "📸 Photographier l'étiquette pour lire son texte",
        "camera_needs_https": "La caméra nécessite https:// (ou localhost). Saisissez le code ci-dessous à la place.",
        "scanner_lib_failed": "Échec du chargement de la bibliothèque de scan",
        "align_barcode": "Alignez le code-barres dans le cadre…",
        "camera_error": "Erreur caméra : {error}",
        "looking_up": "Recherche de {barcode}…",
        "lookup_failed": "Échec de la recherche",
        "invalid_barcode": (
            "Saisissez un code UPC-A/EAN-8/EAN-13 valide, ou une référence/SKU "
            "du fabricant (3 caractères min.)."
        ),
    },
    "form": {
        "title": "Détails du filament",
        "forget": "🗑 Oublier",
        "paste_title_label": "Collez le titre du produit pour un remplissage automatique (facultatif)",
        "paste_title_placeholder": "ex. SUNLU PLA+ 1.75mm Noir 1KG",
        "fill_button": "✨ Remplir",
        "fill_hint": "Trouvez l'annonce, copiez son nom, appuyez sur Remplir.",
        "search_link": "🔍 Rechercher ce code sur le web",
        "material": "Matériau *",
        "brand": "Marque",
        "subtype": "Sous-type / finition",
        "color_name": "Nom de la couleur",
        "color": "Couleur",
        "net_weight": "Poids net (g)",
        "quantity": "Quantité",
        "storage_location": "Emplacement de stockage",
        "category": "Catégorie",
        "optional_placeholder": "facultatif",
        "nozzle_min": "Buse min °C",
        "nozzle_max": "Buse max °C",
        "cost_per_kg": "Coût /kg",
        "note": "Note",
        "submit": "＋ Ajouter à l'inventaire Bambuddy",
        "forgotten": "Oublié — ne se remplira plus automatiquement la prochaine fois",
        "forget_failed": "Échec",
        "manual_entry": "saisi manuellement",
        "also_matches": "Correspond aussi à : {codes}",
        "refill_suffix": " (recharge)",
        "barcode_label": "Code-barres :",
        "parse_failed": "Impossible d'analyser ce titre",
        "parse_request_failed": "Échec de l'analyse",
    },
    "badge": {
        "cache": "mémorisé",
        "ofd": "Open Filament Database",
        "smdb": "SpoolmanDB-Community",
        "label": "lu depuis la photo de l'étiquette — à vérifier attentivement",
        "amazon": "Code Amazon — saisissez-le ci-dessous (je m'en souviendrai)",
        "none": "absent de la base de données — saisissez-le ci-dessous (je m'en souviendrai)",
    },
    "ocr": {
        "loading_recognizer": "Chargement du reconnaisseur de texte (première fois seulement)…",
        "reading_label": "Lecture de l'étiquette…",
        "reading_label_rotated": "Lecture de l'étiquette (pivotée {deg}°)… {percent}%",
        "no_text_found": "Aucun texte trouvé — essayez une photo plus nette et plus rapprochée.",
        "couldnt_read": (
            "Impossible de lire clairement l'étiquette. Essayez une photo plus "
            "rapprochée, à plat et bien éclairée du texte — ou remplissez les "
            "détails ci-dessous."
        ),
        "failed": "Échec OCR : {error}",
    },
    "submit": {
        "material_required": "Le matériau est requis",
        "added": "{count} bobine ajoutée",
        "added_plural": "{count} bobines ajoutées",
        "failed": "Échec",
        "request_failed": "Échec de la requête",
    },
}

JA = {
    "app": {"title": "Filament → Bambuddy"},
    "ptr": {
        "pull": "引っ張って更新",
        "release": "離して更新",
        "refreshing": "更新中…",
    },
    "health": {
        "checking": "Bambuddyを確認中…",
        "connected": "{bambuddy} に接続済み",
        "permission_issue": "権限の問題",
        "not_reachable": "Bambuddyに接続できません",
        "using": "{bambuddy} を使用中",
        "server_error": "サーバーエラー",
    },
    "scan": {
        "refresh_db": "⟳ データベースを更新",
        "refreshing_db": "データベースを更新中…",
        "refresh_updated": "更新完了：OFDバーコード {barcodes} 件、ブランド {brands} 件。",
        "refresh_updated_smdb": " SpoolmanDB-Communityバーコード {count} 件を追加。",
        "refresh_failed": "更新に失敗しました",
        "clear_cache": "🗑 記憶した検索履歴を削除",
        "clear_confirm": "記憶したバーコード検索をすべて忘れますか？（Open Filament Databaseには影響しません）",
        "cleared": "記憶した検索を {count} 件削除しました",
        "cleared_plural": "記憶した検索を {count} 件削除しました",
        "clear_failed": "削除に失敗しました",
        "scan_button": "📷 バーコードをスキャン",
        "stop_camera": "カメラを停止",
        "manual_label": "…またはバーコード/SKU番号を入力",
        "manual_placeholder": "例: 6940082300018",
        "lookup_button": "検索",
        "or_separator": "— または —",
        "ocr_button": "📸 ラベルを撮影してテキストを読み取る",
        "camera_needs_https": "カメラの使用には https:// (またはlocalhost) が必要です。代わりに下にバーコードを入力してください。",
        "scanner_lib_failed": "スキャナーライブラリの読み込みに失敗しました",
        "align_barcode": "枠内にバーコードを合わせてください…",
        "camera_error": "カメラエラー: {error}",
        "looking_up": "{barcode} を検索中…",
        "lookup_failed": "検索に失敗しました",
        "invalid_barcode": "有効なUPC-A/EAN-8/EAN-13バーコード、またはメーカーのSKU/型番（3文字以上）を入力してください。",
    },
    "form": {
        "title": "フィラメントの詳細",
        "forget": "🗑 削除",
        "paste_title_label": "商品タイトルを貼り付けて自動入力（任意）",
        "paste_title_placeholder": "例: SUNLU PLA+ 1.75mm ブラック 1KG",
        "fill_button": "✨ 自動入力",
        "fill_hint": "商品ページを見つけて名前をコピーし、自動入力をタップしてください。",
        "search_link": "🔍 このコードをウェブで検索",
        "material": "素材 *",
        "brand": "ブランド",
        "subtype": "サブタイプ / 仕上げ",
        "color_name": "色名",
        "color": "色",
        "net_weight": "正味重量 (g)",
        "quantity": "数量",
        "storage_location": "保管場所",
        "category": "カテゴリー",
        "optional_placeholder": "任意",
        "nozzle_min": "ノズル最低温度 °C",
        "nozzle_max": "ノズル最高温度 °C",
        "cost_per_kg": "価格 /kg",
        "note": "メモ",
        "submit": "＋ Bambuddy在庫に追加",
        "forgotten": "削除しました — 次回は自動入力されません",
        "forget_failed": "失敗しました",
        "manual_entry": "手動入力",
        "also_matches": "一致するコード: {codes}",
        "refill_suffix": "（リフィル）",
        "barcode_label": "バーコード:",
        "parse_failed": "そのタイトルを解析できませんでした",
        "parse_request_failed": "解析に失敗しました",
    },
    "badge": {
        "cache": "記憶済み",
        "ofd": "Open Filament Database",
        "smdb": "SpoolmanDB-Community",
        "label": "ラベル写真から読み取り — よく確認してください",
        "amazon": "Amazonコード — 下に入力してください（記憶します）",
        "none": "データベースに未登録 — 下に入力してください（記憶します）",
    },
    "ocr": {
        "loading_recognizer": "文字認識エンジンを読み込み中（初回のみ）…",
        "reading_label": "ラベルを読み取り中…",
        "reading_label_rotated": "ラベルを読み取り中（{deg}°回転）… {percent}%",
        "no_text_found": "テキストが見つかりません — より鮮明で近い写真をお試しください。",
        "couldnt_read": (
            "ラベルをはっきり読み取れませんでした。より近く、平らで、明るい場所での"
            "写真をお試しいただくか、下の詳細を入力してください。"
        ),
        "failed": "OCRに失敗しました: {error}",
    },
    "submit": {
        "material_required": "素材は必須です",
        "added": "{count} 個のスプールを追加しました",
        "added_plural": "{count} 個のスプールを追加しました",
        "failed": "失敗しました",
        "request_failed": "リクエストに失敗しました",
    },
}

IT = {
    "app": {"title": "Filament → Bambuddy"},
    "ptr": {
        "pull": "Trascina per aggiornare",
        "release": "Rilascia per aggiornare",
        "refreshing": "Aggiornamento…",
    },
    "health": {
        "checking": "Verifica di Bambuddy…",
        "connected": "Connesso a {bambuddy}",
        "permission_issue": "Problema di autorizzazione",
        "not_reachable": "Bambuddy non raggiungibile",
        "using": "tramite {bambuddy}",
        "server_error": "Errore del server",
    },
    "scan": {
        "refresh_db": "⟳ Aggiorna DB",
        "refreshing_db": "Aggiornamento database…",
        "refresh_updated": "Aggiornato: {barcodes} codici OFD, {brands} marchi.",
        "refresh_updated_smdb": " +{count} codici SpoolmanDB-Community.",
        "refresh_failed": "Aggiornamento non riuscito",
        "clear_cache": "🗑 Cancella ricerche memorizzate",
        "clear_confirm": "Dimenticare tutte le ricerche di codici memorizzate? (Open Filament Database non è interessata.)",
        "cleared": "{count} ricerca memorizzata cancellata",
        "cleared_plural": "{count} ricerche memorizzate cancellate",
        "clear_failed": "Cancellazione non riuscita",
        "scan_button": "📷 Scansiona codice a barre",
        "stop_camera": "Ferma fotocamera",
        "manual_label": "…oppure inserisci il codice a barre/SKU",
        "manual_placeholder": "es. 6940082300018",
        "lookup_button": "Cerca",
        "or_separator": "— oppure —",
        "ocr_button": "📸 Fotografa l'etichetta per leggerne il testo",
        "camera_needs_https": "La fotocamera richiede https:// (o localhost). Digita il codice qui sotto.",
        "scanner_lib_failed": "Caricamento della libreria dello scanner non riuscito",
        "align_barcode": "Allinea il codice a barre nel riquadro…",
        "camera_error": "Errore fotocamera: {error}",
        "looking_up": "Ricerca di {barcode}…",
        "lookup_failed": "Ricerca non riuscita",
        "invalid_barcode": (
            "Inserisci un codice UPC-A/EAN-8/EAN-13 valido, oppure un numero "
            "SKU/articolo del produttore (almeno 3 caratteri)."
        ),
    },
    "form": {
        "title": "Dettagli del filamento",
        "forget": "🗑 Dimentica",
        "paste_title_label": "Incolla il titolo del prodotto per il riempimento automatico (opzionale)",
        "paste_title_placeholder": "es. SUNLU PLA+ 1.75mm Nero 1KG",
        "fill_button": "✨ Compila",
        "fill_hint": "Trova l'annuncio, copia il nome, tocca Compila.",
        "search_link": "🔍 Cerca questo codice sul web",
        "material": "Materiale *",
        "brand": "Marca",
        "subtype": "Sottotipo / finitura",
        "color_name": "Nome colore",
        "color": "Colore",
        "net_weight": "Peso netto (g)",
        "quantity": "Quantità",
        "storage_location": "Posizione di archiviazione",
        "category": "Categoria",
        "optional_placeholder": "opzionale",
        "nozzle_min": "Ugello min °C",
        "nozzle_max": "Ugello max °C",
        "cost_per_kg": "Costo /kg",
        "note": "Nota",
        "submit": "＋ Aggiungi all'inventario Bambuddy",
        "forgotten": "Dimenticato — non verrà compilato automaticamente la prossima volta",
        "forget_failed": "Non riuscito",
        "manual_entry": "inserito manualmente",
        "also_matches": "Corrisponde anche a: {codes}",
        "refill_suffix": " (ricarica)",
        "barcode_label": "Codice a barre:",
        "parse_failed": "Impossibile analizzare quel titolo",
        "parse_request_failed": "Analisi non riuscita",
    },
    "badge": {
        "cache": "memorizzato",
        "ofd": "Open Filament Database",
        "smdb": "SpoolmanDB-Community",
        "label": "letto dalla foto dell'etichetta — controlla attentamente",
        "amazon": "Codice Amazon — inseriscilo qui sotto (lo memorizzerò)",
        "none": "non presente nel database — inseriscilo qui sotto (lo memorizzerò)",
    },
    "ocr": {
        "loading_recognizer": "Caricamento del riconoscitore di testo (solo la prima volta)…",
        "reading_label": "Lettura etichetta…",
        "reading_label_rotated": "Lettura etichetta (ruotata di {deg}°)… {percent}%",
        "no_text_found": "Nessun testo trovato — prova con una foto più nitida e ravvicinata.",
        "couldnt_read": (
            "Impossibile leggere chiaramente l'etichetta. Prova una foto più "
            "ravvicinata, piatta e ben illuminata del testo — oppure compila i "
            "dettagli qui sotto."
        ),
        "failed": "OCR non riuscito: {error}",
    },
    "submit": {
        "material_required": "Il materiale è obbligatorio",
        "added": "Aggiunta {count} bobina",
        "added_plural": "Aggiunte {count} bobine",
        "failed": "Non riuscito",
        "request_failed": "Richiesta non riuscita",
    },
}

KO = {
    "app": {"title": "Filament → Bambuddy"},
    "ptr": {
        "pull": "당겨서 새로고침",
        "release": "놓아서 새로고침",
        "refreshing": "새로고침 중…",
    },
    "health": {
        "checking": "Bambuddy 확인 중…",
        "connected": "{bambuddy}에 연결됨",
        "permission_issue": "권한 문제",
        "not_reachable": "Bambuddy에 연결할 수 없음",
        "using": "{bambuddy} 사용 중",
        "server_error": "서버 오류",
    },
    "scan": {
        "refresh_db": "⟳ DB 새로고침",
        "refreshing_db": "데이터베이스 업데이트 중…",
        "refresh_updated": "업데이트됨: OFD 바코드 {barcodes}개, 브랜드 {brands}개.",
        "refresh_updated_smdb": " SpoolmanDB-Community 바코드 {count}개 추가.",
        "refresh_failed": "업데이트 실패",
        "clear_cache": "🗑 저장된 검색 기록 지우기",
        "clear_confirm": "저장된 모든 바코드 검색 기록을 삭제할까요? (Open Filament Database에는 영향이 없습니다.)",
        "cleared": "저장된 검색 기록 {count}개를 삭제했습니다",
        "cleared_plural": "저장된 검색 기록 {count}개를 삭제했습니다",
        "clear_failed": "삭제 실패",
        "scan_button": "📷 바코드 스캔",
        "stop_camera": "카메라 정지",
        "manual_label": "…또는 바코드/SKU 번호 입력",
        "manual_placeholder": "예: 6940082300018",
        "lookup_button": "조회",
        "or_separator": "— 또는 —",
        "ocr_button": "📸 라벨을 촬영하여 텍스트 읽기",
        "camera_needs_https": "카메라를 사용하려면 https:// (또는 localhost)가 필요합니다. 대신 아래에 바코드를 입력하세요.",
        "scanner_lib_failed": "스캐너 라이브러리를 불러오지 못했습니다",
        "align_barcode": "프레임 안에 바코드를 맞추세요…",
        "camera_error": "카메라 오류: {error}",
        "looking_up": "{barcode} 조회 중…",
        "lookup_failed": "조회 실패",
        "invalid_barcode": "유효한 UPC-A/EAN-8/EAN-13 바코드나 제조사 SKU/품번(3자 이상)을 입력하세요.",
    },
    "form": {
        "title": "필라멘트 세부 정보",
        "forget": "🗑 삭제",
        "paste_title_label": "제품 제목을 붙여넣어 자동 완성 (선택 사항)",
        "paste_title_placeholder": "예: SUNLU PLA+ 1.75mm 블랙 1KG",
        "fill_button": "✨ 채우기",
        "fill_hint": "상품 페이지를 찾아 이름을 복사한 후 채우기를 누르세요.",
        "search_link": "🔍 이 코드로 웹 검색",
        "material": "재질 *",
        "brand": "브랜드",
        "subtype": "하위 유형 / 마감",
        "color_name": "색상 이름",
        "color": "색상",
        "net_weight": "순중량 (g)",
        "quantity": "수량",
        "storage_location": "보관 위치",
        "category": "카테고리",
        "optional_placeholder": "선택 사항",
        "nozzle_min": "노즐 최저 °C",
        "nozzle_max": "노즐 최고 °C",
        "cost_per_kg": "가격 /kg",
        "note": "메모",
        "submit": "＋ Bambuddy 재고에 추가",
        "forgotten": "삭제됨 — 다음에는 자동으로 채워지지 않습니다",
        "forget_failed": "실패",
        "manual_entry": "수동 입력됨",
        "also_matches": "다음과도 일치: {codes}",
        "refill_suffix": " (리필)",
        "barcode_label": "바코드:",
        "parse_failed": "해당 제목을 분석할 수 없습니다",
        "parse_request_failed": "분석 실패",
    },
    "badge": {
        "cache": "저장됨",
        "ofd": "Open Filament Database",
        "smdb": "SpoolmanDB-Community",
        "label": "라벨 사진에서 읽음 — 주의해서 확인하세요",
        "amazon": "Amazon 코드 — 아래에 입력하세요 (기억해 둘게요)",
        "none": "데이터베이스에 없음 — 아래에 입력하세요 (기억해 둘게요)",
    },
    "ocr": {
        "loading_recognizer": "텍스트 인식기 로딩 중 (최초 1회만)…",
        "reading_label": "라벨 읽는 중…",
        "reading_label_rotated": "라벨 읽는 중 ({deg}° 회전)… {percent}%",
        "no_text_found": "텍스트를 찾을 수 없습니다 — 더 선명하고 가까운 사진을 시도해 보세요.",
        "couldnt_read": (
            "라벨을 명확하게 읽을 수 없습니다. 더 가깝고 평평하며 밝은 곳에서 "
            "사양 텍스트 사진을 다시 찍어보거나, 아래에 직접 세부 정보를 입력하세요."
        ),
        "failed": "OCR 실패: {error}",
    },
    "submit": {
        "material_required": "재질은 필수입니다",
        "added": "스풀 {count}개 추가됨",
        "added_plural": "스풀 {count}개 추가됨",
        "failed": "실패",
        "request_failed": "요청 실패",
    },
}

PT_BR = {
    "app": {"title": "Filament → Bambuddy"},
    "ptr": {
        "pull": "Puxe para atualizar",
        "release": "Solte para atualizar",
        "refreshing": "Atualizando…",
    },
    "health": {
        "checking": "Verificando o Bambuddy…",
        "connected": "Conectado a {bambuddy}",
        "permission_issue": "Problema de permissão",
        "not_reachable": "Bambuddy inacessível",
        "using": "usando {bambuddy}",
        "server_error": "Erro do servidor",
    },
    "scan": {
        "refresh_db": "⟳ Atualizar BD",
        "refreshing_db": "Atualizando banco de dados…",
        "refresh_updated": "Atualizado: {barcodes} códigos OFD, {brands} marcas.",
        "refresh_updated_smdb": " +{count} códigos SpoolmanDB-Community.",
        "refresh_failed": "Falha ao atualizar",
        "clear_cache": "🗑 Limpar buscas memorizadas",
        "clear_confirm": "Esquecer todas as buscas de código memorizadas? (O Open Filament Database não é afetado.)",
        "cleared": "{count} busca memorizada apagada",
        "cleared_plural": "{count} buscas memorizadas apagadas",
        "clear_failed": "Falha ao limpar",
        "scan_button": "📷 Escanear código de barras",
        "stop_camera": "Parar câmera",
        "manual_label": "…ou digite o código de barras/SKU",
        "manual_placeholder": "ex.: 6940082300018",
        "lookup_button": "Buscar",
        "or_separator": "— ou —",
        "ocr_button": "📸 Fotografar a etiqueta para ler o texto",
        "camera_needs_https": "A câmera precisa de https:// (ou localhost). Digite o código abaixo.",
        "scanner_lib_failed": "Falha ao carregar a biblioteca do scanner",
        "align_barcode": "Alinhe o código de barras dentro do quadro…",
        "camera_error": "Erro na câmera: {error}",
        "looking_up": "Buscando {barcode}…",
        "lookup_failed": "Falha na busca",
        "invalid_barcode": (
            "Digite um código UPC-A/EAN-8/EAN-13 válido, ou um número de "
            "SKU/artigo do fabricante (3+ caracteres)."
        ),
    },
    "form": {
        "title": "Detalhes do filamento",
        "forget": "🗑 Esquecer",
        "paste_title_label": "Cole o título do produto para preencher automaticamente (opcional)",
        "paste_title_placeholder": "ex.: SUNLU PLA+ 1.75mm Preto 1KG",
        "fill_button": "✨ Preencher",
        "fill_hint": "Encontre o anúncio, copie o nome, toque em Preencher.",
        "search_link": "🔍 Pesquisar este código na web",
        "material": "Material *",
        "brand": "Marca",
        "subtype": "Subtipo / acabamento",
        "color_name": "Nome da cor",
        "color": "Cor",
        "net_weight": "Peso líquido (g)",
        "quantity": "Quantidade",
        "storage_location": "Local de armazenamento",
        "category": "Categoria",
        "optional_placeholder": "opcional",
        "nozzle_min": "Bico mín °C",
        "nozzle_max": "Bico máx °C",
        "cost_per_kg": "Custo /kg",
        "note": "Observação",
        "submit": "＋ Adicionar ao inventário do Bambuddy",
        "forgotten": "Esquecido — não será preenchido automaticamente na próxima vez",
        "forget_failed": "Falhou",
        "manual_entry": "inserido manualmente",
        "also_matches": "Também corresponde a: {codes}",
        "refill_suffix": " (refil)",
        "barcode_label": "Código de barras:",
        "parse_failed": "Não foi possível analisar esse título",
        "parse_request_failed": "Falha na análise",
    },
    "badge": {
        "cache": "memorizado",
        "ofd": "Open Filament Database",
        "smdb": "SpoolmanDB-Community",
        "label": "lido da foto da etiqueta — verifique com cuidado",
        "amazon": "Código da Amazon — digite abaixo (vou lembrar)",
        "none": "não está no banco de dados — digite abaixo (vou lembrar)",
    },
    "ocr": {
        "loading_recognizer": "Carregando reconhecedor de texto (apenas na primeira vez)…",
        "reading_label": "Lendo etiqueta…",
        "reading_label_rotated": "Lendo etiqueta (girada {deg}°)… {percent}%",
        "no_text_found": "Nenhum texto encontrado — tente uma foto mais nítida e próxima.",
        "couldnt_read": (
            "Não foi possível ler a etiqueta claramente. Tente uma foto mais "
            "próxima, plana e bem iluminada do texto — ou preencha os "
            "detalhes abaixo."
        ),
        "failed": "Falha no OCR: {error}",
    },
    "submit": {
        "material_required": "O material é obrigatório",
        "added": "{count} carretel adicionado",
        "added_plural": "{count} carretéis adicionados",
        "failed": "Falhou",
        "request_failed": "Falha na solicitação",
    },
}

ZH_CN = {
    "app": {"title": "Filament → Bambuddy"},
    "ptr": {
        "pull": "下拉刷新",
        "release": "松开刷新",
        "refreshing": "正在刷新…",
    },
    "health": {
        "checking": "正在检查 Bambuddy…",
        "connected": "已连接到 {bambuddy}",
        "permission_issue": "权限问题",
        "not_reachable": "无法连接到 Bambuddy",
        "using": "使用 {bambuddy}",
        "server_error": "服务器错误",
    },
    "scan": {
        "refresh_db": "⟳ 刷新数据库",
        "refreshing_db": "正在更新数据库…",
        "refresh_updated": "已更新：{barcodes} 个 OFD 条码，{brands} 个品牌。",
        "refresh_updated_smdb": " 另加 {count} 个 SpoolmanDB-Community 条码。",
        "refresh_failed": "刷新失败",
        "clear_cache": "🗑 清除已记住的查询",
        "clear_confirm": "要忘记所有已记住的条码查询吗？（不会影响 Open Filament Database）",
        "cleared": "已清除 {count} 条记住的查询",
        "cleared_plural": "已清除 {count} 条记住的查询",
        "clear_failed": "清除失败",
        "scan_button": "📷 扫描条码",
        "stop_camera": "停止摄像头",
        "manual_label": "…或输入条码/SKU 编号",
        "manual_placeholder": "例如 6940082300018",
        "lookup_button": "查询",
        "or_separator": "— 或 —",
        "ocr_button": "📸 拍摄标签以读取文字",
        "camera_needs_https": "摄像头需要 https://（或 localhost）。请改为在下方输入条码。",
        "scanner_lib_failed": "扫描库加载失败",
        "align_barcode": "请将条码对准框内…",
        "camera_error": "摄像头错误：{error}",
        "looking_up": "正在查询 {barcode}…",
        "lookup_failed": "查询失败",
        "invalid_barcode": "请输入有效的 UPC-A/EAN-8/EAN-13 条码，或制造商 SKU/货号（至少 3 个字符）。",
    },
    "form": {
        "title": "耗材详情",
        "forget": "🗑 忘记",
        "paste_title_label": "粘贴产品标题以自动填充（可选）",
        "paste_title_placeholder": "例如 SUNLU PLA+ 1.75mm 黑色 1KG",
        "fill_button": "✨ 填充",
        "fill_hint": "找到商品页面，复制其名称，点击填充。",
        "search_link": "🔍 在网上搜索此代码",
        "material": "材料 *",
        "brand": "品牌",
        "subtype": "子类型 / 表面处理",
        "color_name": "颜色名称",
        "color": "颜色",
        "net_weight": "净重 (g)",
        "quantity": "数量",
        "storage_location": "存放位置",
        "category": "分类",
        "optional_placeholder": "可选",
        "nozzle_min": "喷嘴最低温度 °C",
        "nozzle_max": "喷嘴最高温度 °C",
        "cost_per_kg": "价格 /kg",
        "note": "备注",
        "submit": "＋ 添加到 Bambuddy 库存",
        "forgotten": "已忘记 — 下次将不会自动填充",
        "forget_failed": "失败",
        "manual_entry": "手动输入",
        "also_matches": "也匹配：{codes}",
        "refill_suffix": "（补充装）",
        "barcode_label": "条码：",
        "parse_failed": "无法解析该标题",
        "parse_request_failed": "解析失败",
    },
    "badge": {
        "cache": "已记住",
        "ofd": "Open Filament Database",
        "smdb": "SpoolmanDB-Community",
        "label": "从标签照片读取 — 请仔细核对",
        "amazon": "亚马逊代码 — 请在下方输入（我会记住）",
        "none": "数据库中未找到 — 请在下方输入（我会记住）",
    },
    "ocr": {
        "loading_recognizer": "正在加载文字识别引擎（仅首次）…",
        "reading_label": "正在读取标签…",
        "reading_label_rotated": "正在读取标签（旋转 {deg}°）… {percent}%",
        "no_text_found": "未找到文字 — 请尝试更清晰、更近的照片。",
        "couldnt_read": (
            "无法清晰读取标签。请尝试拍摄更近、更平整、光线更好的规格文字照片 — "
            "或在下方手动填写详情。"
        ),
        "failed": "OCR 失败：{error}",
    },
    "submit": {
        "material_required": "材料为必填项",
        "added": "已添加 {count} 卷",
        "added_plural": "已添加 {count} 卷",
        "failed": "失败",
        "request_failed": "请求失败",
    },
}

ZH_TW = {
    "app": {"title": "Filament → Bambuddy"},
    "ptr": {
        "pull": "下拉重新整理",
        "release": "放開以重新整理",
        "refreshing": "重新整理中…",
    },
    "health": {
        "checking": "正在檢查 Bambuddy…",
        "connected": "已連線至 {bambuddy}",
        "permission_issue": "權限問題",
        "not_reachable": "無法連線至 Bambuddy",
        "using": "使用 {bambuddy}",
        "server_error": "伺服器錯誤",
    },
    "scan": {
        "refresh_db": "⟳ 重新整理資料庫",
        "refreshing_db": "正在更新資料庫…",
        "refresh_updated": "已更新：{barcodes} 個 OFD 條碼，{brands} 個品牌。",
        "refresh_updated_smdb": " 另加 {count} 個 SpoolmanDB-Community 條碼。",
        "refresh_failed": "更新失敗",
        "clear_cache": "🗑 清除已記住的查詢",
        "clear_confirm": "要忘記所有已記住的條碼查詢嗎？（不會影響 Open Filament Database）",
        "cleared": "已清除 {count} 筆記住的查詢",
        "cleared_plural": "已清除 {count} 筆記住的查詢",
        "clear_failed": "清除失敗",
        "scan_button": "📷 掃描條碼",
        "stop_camera": "停止攝影機",
        "manual_label": "…或輸入條碼/SKU 編號",
        "manual_placeholder": "例如 6940082300018",
        "lookup_button": "查詢",
        "or_separator": "— 或 —",
        "ocr_button": "📸 拍攝標籤以讀取文字",
        "camera_needs_https": "攝影機需要 https://（或 localhost）。請改為在下方輸入條碼。",
        "scanner_lib_failed": "掃描器函式庫載入失敗",
        "align_barcode": "請將條碼對準框內…",
        "camera_error": "攝影機錯誤：{error}",
        "looking_up": "正在查詢 {barcode}…",
        "lookup_failed": "查詢失敗",
        "invalid_barcode": "請輸入有效的 UPC-A/EAN-8/EAN-13 條碼，或製造商 SKU/貨號（至少 3 個字元）。",
    },
    "form": {
        "title": "線材詳細資料",
        "forget": "🗑 忘記",
        "paste_title_label": "貼上產品標題以自動填入（選填）",
        "paste_title_placeholder": "例如 SUNLU PLA+ 1.75mm 黑色 1KG",
        "fill_button": "✨ 自動填入",
        "fill_hint": "找到商品頁面，複製其名稱，點擊自動填入。",
        "search_link": "🔍 在網路上搜尋此代碼",
        "material": "材質 *",
        "brand": "品牌",
        "subtype": "子類型 / 表面處理",
        "color_name": "顏色名稱",
        "color": "顏色",
        "net_weight": "淨重 (g)",
        "quantity": "數量",
        "storage_location": "存放位置",
        "category": "分類",
        "optional_placeholder": "選填",
        "nozzle_min": "噴嘴最低溫度 °C",
        "nozzle_max": "噴嘴最高溫度 °C",
        "cost_per_kg": "價格 /kg",
        "note": "備註",
        "submit": "＋ 加入 Bambuddy 庫存",
        "forgotten": "已忘記 — 下次將不會自動填入",
        "forget_failed": "失敗",
        "manual_entry": "手動輸入",
        "also_matches": "也符合：{codes}",
        "refill_suffix": "（補充包）",
        "barcode_label": "條碼：",
        "parse_failed": "無法解析該標題",
        "parse_request_failed": "解析失敗",
    },
    "badge": {
        "cache": "已記住",
        "ofd": "Open Filament Database",
        "smdb": "SpoolmanDB-Community",
        "label": "從標籤照片讀取 — 請仔細核對",
        "amazon": "Amazon 代碼 — 請在下方輸入（我會記住）",
        "none": "資料庫中找不到 — 請在下方輸入（我會記住）",
    },
    "ocr": {
        "loading_recognizer": "正在載入文字辨識引擎（僅限首次）…",
        "reading_label": "正在讀取標籤…",
        "reading_label_rotated": "正在讀取標籤（旋轉 {deg}°）… {percent}%",
        "no_text_found": "找不到文字 — 請嘗試更清晰、更近的照片。",
        "couldnt_read": (
            "無法清楚讀取標籤。請嘗試拍攝更近、更平整、光線更好的規格文字照片 — "
            "或在下方手動填寫詳細資料。"
        ),
        "failed": "OCR 失敗：{error}",
    },
    "submit": {
        "material_required": "材質為必填項目",
        "added": "已新增 {count} 捲",
        "added_plural": "已新增 {count} 捲",
        "failed": "失敗",
        "request_failed": "請求失敗",
    },
}

TR = {
    "app": {"title": "Filament → Bambuddy"},
    "ptr": {
        "pull": "Yenilemek için çekin",
        "release": "Yenilemek için bırakın",
        "refreshing": "Yenileniyor…",
    },
    "health": {
        "checking": "Bambuddy kontrol ediliyor…",
        "connected": "{bambuddy} adresine bağlanıldı",
        "permission_issue": "İzin sorunu",
        "not_reachable": "Bambuddy'ye ulaşılamıyor",
        "using": "{bambuddy} kullanılıyor",
        "server_error": "Sunucu hatası",
    },
    "scan": {
        "refresh_db": "⟳ Veritabanını Yenile",
        "refreshing_db": "Veritabanı güncelleniyor…",
        "refresh_updated": "Güncellendi: {barcodes} OFD barkodu, {brands} marka.",
        "refresh_updated_smdb": " +{count} SpoolmanDB-Community barkodu.",
        "refresh_failed": "Yenileme başarısız oldu",
        "clear_cache": "🗑 Hatırlanan aramaları temizle",
        "clear_confirm": "Hatırlanan tüm barkod aramaları unutulsun mu? (Open Filament Database etkilenmez.)",
        "cleared": "{count} hatırlanan arama silindi",
        "cleared_plural": "{count} hatırlanan arama silindi",
        "clear_failed": "Temizleme başarısız oldu",
        "scan_button": "📷 Barkod tara",
        "stop_camera": "Kamerayı durdur",
        "manual_label": "…veya barkod/SKU numarasını girin",
        "manual_placeholder": "örn. 6940082300018",
        "lookup_button": "Ara",
        "or_separator": "— veya —",
        "ocr_button": "📸 Metni okumak için etiketi fotoğraflayın",
        "camera_needs_https": "Kamera için https:// (veya localhost) gerekir. Bunun yerine barkodu aşağıya yazın.",
        "scanner_lib_failed": "Tarayıcı kütüphanesi yüklenemedi",
        "align_barcode": "Barkodu çerçeve içine hizalayın…",
        "camera_error": "Kamera hatası: {error}",
        "looking_up": "{barcode} aranıyor…",
        "lookup_failed": "Arama başarısız oldu",
        "invalid_barcode": (
            "Geçerli bir UPC-A/EAN-8/EAN-13 barkodu veya üretici SKU/ürün "
            "numarası (en az 3 karakter) girin."
        ),
    },
    "form": {
        "title": "Filament ayrıntıları",
        "forget": "🗑 Unut",
        "paste_title_label": "Otomatik doldurmak için ürün başlığını yapıştırın (isteğe bağlı)",
        "paste_title_placeholder": "örn. SUNLU PLA+ 1.75mm Siyah 1KG",
        "fill_button": "✨ Doldur",
        "fill_hint": "İlanı bulun, adını kopyalayın, Doldur'a dokunun.",
        "search_link": "🔍 Bu kodu web'de ara",
        "material": "Malzeme *",
        "brand": "Marka",
        "subtype": "Alt tür / yüzey",
        "color_name": "Renk adı",
        "color": "Renk",
        "net_weight": "Net ağırlık (g)",
        "quantity": "Adet",
        "storage_location": "Depolama konumu",
        "category": "Kategori",
        "optional_placeholder": "isteğe bağlı",
        "nozzle_min": "Nozül min °C",
        "nozzle_max": "Nozül maks °C",
        "cost_per_kg": "Maliyet /kg",
        "note": "Not",
        "submit": "＋ Bambuddy envanterine ekle",
        "forgotten": "Unutuldu — bir dahaki sefere otomatik doldurulmayacak",
        "forget_failed": "Başarısız oldu",
        "manual_entry": "manuel girildi",
        "also_matches": "Şununla da eşleşiyor: {codes}",
        "refill_suffix": " (yeniden dolum)",
        "barcode_label": "Barkod:",
        "parse_failed": "Bu başlık ayrıştırılamadı",
        "parse_request_failed": "Ayrıştırma başarısız oldu",
    },
    "badge": {
        "cache": "hatırlandı",
        "ofd": "Open Filament Database",
        "smdb": "SpoolmanDB-Community",
        "label": "etiket fotoğrafından okundu — dikkatlice kontrol edin",
        "amazon": "Amazon kodu — aşağıya girin (hatırlayacağım)",
        "none": "veritabanında yok — aşağıya girin (hatırlayacağım)",
    },
    "ocr": {
        "loading_recognizer": "Metin tanıyıcı yükleniyor (yalnızca ilk seferde)…",
        "reading_label": "Etiket okunuyor…",
        "reading_label_rotated": "Etiket okunuyor ({deg}° döndürüldü)… %{percent}",
        "no_text_found": "Metin bulunamadı — daha net, daha yakın bir fotoğraf deneyin.",
        "couldnt_read": (
            "Etiket net olarak okunamadı. Teknik bilgi metninin daha yakın, düz "
            "ve iyi aydınlatılmış bir fotoğrafını deneyin — veya aşağıdaki "
            "ayrıntıları kendiniz doldurun."
        ),
        "failed": "OCR başarısız oldu: {error}",
    },
    "submit": {
        "material_required": "Malzeme gereklidir",
        "added": "{count} makara eklendi",
        "added_plural": "{count} makara eklendi",
        "failed": "Başarısız oldu",
        "request_failed": "İstek başarısız oldu",
    },
}

# All available translations. Language codes match Bambuddy's own supported
# set (frontend/src/i18n/index.ts's SUPPORTED_LNGS) but are kept fully
# lowercase here (e.g. "pt-br", not "pt-BR") for consistent
# case-insensitive matching against query params / cookies in resolve_locale
# below — BCP-47 region subtag casing carries no semantic meaning.
TRANSLATIONS = {
    "en": EN,
    "de": DE,
    "es": ES,
    "fr": FR,
    "ja": JA,
    "it": IT,
    "ko": KO,
    "pt-br": PT_BR,
    "zh-cn": ZH_CN,
    "zh-tw": ZH_TW,
    "tr": TR,
}

DEFAULT_LANG = "en"
SUPPORTED_LANGS = sorted(TRANSLATIONS)


def get_translation(lang: str, key: str, **kwargs: Any) -> str:
    """Get a translation string by key with optional interpolation.

    Args:
        lang: Language code (e.g., 'en', 'de').
        key: Dot-separated key path (e.g., 'health.connected').
        **kwargs: Values to interpolate into the string via str.format().

    Returns:
        Translated string, or the key itself if not found in either the
        requested language or the English fallback.
    """
    translations = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG])

    keys = key.split(".")
    value: Any = translations
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            # Key not found in the requested language — fall back to English.
            value = TRANSLATIONS[DEFAULT_LANG]
            for k2 in keys:
                if isinstance(value, dict) and k2 in value:
                    value = value[k2]
                else:
                    return key  # Not found in the fallback either.
            break

    if isinstance(value, str):
        try:
            return value.format(**kwargs)
        except KeyError:
            return value

    return key


class Translator:
    """Helper class for translations bound to a specific language."""

    def __init__(self, lang: str = DEFAULT_LANG):
        self.lang = lang if lang in TRANSLATIONS else DEFAULT_LANG

    def t(self, key: str, **kwargs: Any) -> str:
        """Translate a key."""
        return get_translation(self.lang, key, **kwargs)


def resolve_locale(
    accept_language_header: str | None,
    query_lang: str | None = None,
    cookie_lang: str | None = None,
) -> str:
    """Resolve the active language for a request.

    Priority: an explicit ?lang= query override, then a previously-set
    language cookie, then the browser's Accept-Language header, then the
    default. Query/cookie values are matched case-insensitively against the
    supported set; Accept-Language is parsed permissively (region subtags
    like "en-US" fall back to their base "en").
    """
    for candidate in (query_lang, cookie_lang):
        if candidate and candidate.strip().lower() in TRANSLATIONS:
            return candidate.strip().lower()

    if accept_language_header:
        for part in accept_language_header.split(","):
            code = part.split(";")[0].strip().lower()
            if not code:
                continue
            if code in TRANSLATIONS:
                return code
            base = code.split("-")[0]
            if base in TRANSLATIONS:
                return base

    return DEFAULT_LANG
