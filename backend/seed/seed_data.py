"""
Initial data for MongoDB, ported from shared/mock-data.js (the same
catalog the frontend used before this backend existed). Once seeded,
MongoDB — not this file — is the source of truth; re-running seed.py
overwrites these collections back to this starting point.

Every dict's "id" becomes the document's _id (see services/common.py).
"""

PRODUCTS = [
    {"id":1,"sku":"KID-VRD-01","cat":"kiddush","catLabel":"גביעי קידוש","name":'גביע קידוש "ורדית"',"price":420,"oldPrice":None,"badge":"new",
     "short":"גביע קידוש מכסף סטרלינג, עם חריטת עלים עדינה ובסיס יציב.",
     "desc":'גביע קידוש קלאסי המיוצר בעבודת יד מכסף סטרלינג 925. דגם "ורדית" מתאפיין בחריטה בוטנית עדינה המקיפה את גוף הגביע, ובבסיס רחב המעניק יציבות מרבית על השולחן. מתאים כמתנה לחתונה, בר מצווה או לשולחן השבת בבית.',
     "material":"כסף סטרלינג 925","dim":"גובה 16 ס״מ, קוטר 7 ס״מ","stock":9,"threshold":4,"status":"active","sold":34},
    {"id":2,"sku":"CND-ORZ-02","cat":"candles","catLabel":"פמוטים","name":'זוג פמוטי "אור זך"',"price":640,"oldPrice":760,"badge":"sale",
     "short":"זוג פמוטי שבת מינימליסטיים מכסף מוברש, בקו עיצוב נקי ומודרני.",
     "desc":"זוג פמוטי שבת בקו עיצוב צנוע ומדויק, המשלב פליז מצופה כסף מוברש עם גימור מט. הצורה הגיאומטרית הנקייה הופכת אותם למרכז שולחן אלגנטי המתאים גם לבית מודרני. נמכרים בזוג באריזת מתנה.",
     "material":"פליז מצופה כסף מוברש","dim":"גובה 14 ס״מ ליחידה","stock":3,"threshold":4,"status":"active","sold":27},
    {"id":3,"sku":"SHB-PTS-03","cat":"shabbat","catLabel":"מוצרי שבת","name":'סכין חלה מוכספת "פטיש"',"price":340,"oldPrice":None,"badge":None,
     "short":"סכין חלה מכסף עם ידית מנוקדת בפטיש, ולהב חד ומשונן.",
     "desc":"סכין חלה קלאסית עם ידית כסף בעבודת ניקוב-פטיש (hammered) המעניקה מרקם עדין ונוצץ. הלהב המשונן חד ונוח לפריסה, וגודלה המשפחתי הופך אותה למרכזית על שולחן השבת. מתנה יפה במיוחד לבית חדש.",
     "material":"כסף מצופה, פלדת אל-חלד","dim":"אורך 33 ס״מ","stock":14,"threshold":5,"status":"active","sold":41},
    {"id":14,"sku":"SHB-SVT-14","cat":"shabbat","catLabel":"מוצרי שבת","name":'סכין חלה חרוטה "שבת ויום טוב"',"price":420,"oldPrice":None,"badge":"new",
     "short":'סכין חלה מכסף עם חריטת "שבת ויום טוב" על הלהב וידית מעוצבת.',
     "desc":'סכין חלה מהודרת עם חריטת "שבת ויום טוב" לאורך הלהב המלוטש, וידית כסף בתבנית שריג עדינה המסתיימת בכדור כסוף. שילוב של פונקציונליות והידור, ומתנה משמעותית לחג ולשבת.',
     "material":"כסף מצופה, פלדת אל-חלד","dim":"אורך 34 ס״מ","stock":2,"threshold":5,"status":"active","sold":18},
    {"id":4,"sku":"HAV-BSM-04","cat":"havdalah","catLabel":"הבדלה","name":'סט הבדלה "בשמים"',"price":520,"oldPrice":None,"badge":"new",
     "short":"סט הבדלה הכולל גביע, קופסת בשמים ומעמד לנר, בגימור כסף מלוטש.",
     "desc":"סט הבדלה שלם הכולל גביע יין, קופסת בשמים מחוררת ומעמד נר הבדלה, כולם בגימור כסף מלוטש אחיד. עיצוב מודרני שנשען על קווים נקיים, מוגש בקופסת עץ מרופדת המתאימה גם למתנה.",
     "material":"כסף מצופה, בסיס עץ","dim":"סט הכולל 3 פריטים","stock":7,"threshold":4,"status":"active","sold":22},
    {"id":5,"sku":"GFT-MZD-05","cat":"gifts","catLabel":"מתנות","name":"מזוזת כסף מעוצבת","price":210,"oldPrice":None,"badge":None,
     "short":"מזוזה מכסף מעוצב בעבודת פיליגרן עדינה, מתנת בית קלאסית ומהודרת.",
     "desc":"מזוזה מכסף עם עבודת פיליגרן עדינה ותבליט פרחוני עוטף לכל אורך הבית. אינה כוללת קלף. מגיעה באריזת מתנה מהודרת, ומהווה מחווה אלגנטית לבית חדש.",
     "material":"כסף מצופה, עבודת פיליגרן","dim":"12 ס״מ","stock":20,"threshold":6,"status":"active","sold":55},
    {"id":6,"sku":"SLV-MRV-06","cat":"silverware","catLabel":"כלי כסף","name":"סט קינוח \"מרווה\" (6 יח')","price":340,"oldPrice":390,"badge":"sale",
     "short":"סט 6 כפיות קינוח מכסף מצופה, בגימור מט עדין וקו מודרני.",
     "desc":"סט הכולל 6 כפיות קינוח מכסף מצופה, בגימור מט המונע טביעות אצבע ומעניק מראה עכשווי. מתאים לשימוש יומיומי או לאירוח חגיגי, ומגיע בקופסת אחסון מרופדת בד.",
     "material":"כסף מצופה, גימור מט","dim":"אורך 13 ס״מ ליחידה","stock":11,"threshold":5,"status":"active","sold":30},
    {"id":7,"sku":"KID-MIN-07","cat":"kiddush","catLabel":"גביעי קידוש","name":'גביע קידוש "מינימל"',"price":340,"oldPrice":None,"badge":None,
     "short":"גביע קידוש בקו נקי וגיאומטרי, מכסף מוברש ללא קישוט עודף.",
     "desc":'לצד הדגמים המסורתיים, "מינימל" מציע פרשנות עכשווית לגביע הקידוש: קו ישר, גימור כסף מוברש אחיד וללא חריטה, לבית שאוהב עיצוב שקט ומדויק.',
     "material":"כסף סטרלינג מוברש","dim":"גובה 13 ס״מ","stock":0,"threshold":4,"status":"out","sold":15},
    {"id":8,"sku":"SLV-ELP-08","cat":"silverware","catLabel":"כלי כסף","name":'מגש הגשה "אליפסה"',"price":480,"oldPrice":None,"badge":"new",
     "short":"מגש הגשה אליפטי מכסף מלוטש, לשולחן חג או לאירוח יומיומי.",
     "desc":"מגש הגשה בצורת אליפסה, מכסף מלוטש בעל שוליים מוגבהים עדינים. גודלו מאפשר הגשת מארזי מתנה, פירות או קינוחים בטקס מרשים. ניתן לחריטה אישית בהזמנה מיוחדת.",
     "material":"כסף מצופה מלוטש","dim":"34×22 ס״מ","stock":6,"threshold":4,"status":"active","sold":12},
    {"id":9,"sku":"KID-ZMR-09","cat":"kiddush","catLabel":"גביעי קידוש","name":'גביע קידוש "זמורה"',"price":390,"oldPrice":None,"badge":"new",
     "short":"גביע קידוש כסף עם שרשרת עיטור וצרור ענבים כסוף, לצד גימור פנים מוזהב.",
     "desc":"גביע קידוש כסף בעל גוף מעוגל ואלגנטי, מעוטר בשרשרת כסף עדינה וצרור ענבים תלת-ממדי המקיף את צוואר הגביע — מחווה לברכת היין. פנים הגביע מוזהב, בהתאם למסורת גביעי הקידוש ההדורים.",
     "material":"כסף 925, פנים מוזהב","dim":"גובה 17 ס״מ","stock":8,"threshold":4,"status":"active","sold":19},
    {"id":10,"sku":"MEN-KNC-10","cat":"menorahs","catLabel":"חנוכיות","name":'חנוכיית "קונכית כסף"',"price":560,"oldPrice":None,"badge":"new",
     "short":"חנוכיה כסופה בעיצוב גלי מסתלסל, עם בסיס פעמון יציב.",
     "desc":"חנוכיה בעלת קו זרימה מסתלסל וגלי, המזכיר קונכיה, עם שמונה זרועות ושמש. הבסיס הרחב בצורת פעמון מעניק יציבות מרבית, וההשתקפות המבריקה של הכסף המלוטש הופכת אותה למרכזית בכל שולחן חנוכה.",
     "material":"כסף מצופה מלוטש","dim":"גובה 22 ס״מ","stock":5,"threshold":5,"status":"active","sold":24},
    {"id":11,"sku":"MEN-KSH-11","cat":"menorahs","catLabel":"חנוכיות","name":'חנוכיית "קשת"',"price":610,"oldPrice":680,"badge":"sale",
     "short":"חנוכיה בעיצוב קשתות סימטריות, קו נקי ומודרני על בסיס אליפטי.",
     "desc":"חנוכיה מינימליסטית המורכבת משמונה קשתות כסף סימטריות הנפגשות בשמש המרכזית, על גבי בסיס אליפטי יציב. עיצוב עכשווי ונקי המתאים גם לבית מודרני לצד המסורת.",
     "material":"כסף מצופה מלוטש","dim":"רוחב 30 ס״מ","stock":9,"threshold":5,"status":"active","sold":31},
    {"id":12,"sku":"MEN-ASF-12","cat":"menorahs","catLabel":"חנוכיות","name":'חנוכיית "אספנים" מפוארת',"price":1450,"oldPrice":None,"badge":"new",
     "short":"חנוכיית פאר עם תבליטי פרחים וגלילים, לאספנים ולבתים חגיגיים.",
     "desc":"חנוכיה מפוארת ועשירה בפרטים, עם זרועות מסולסלות מעוטרות בתבליטי פרחים ועלים, גוף מרכזי גבוה ובסיס רחב ומעוטר. פריט פרימיום ליודעי ערך, המשלב אמנות כסף מסורתית עם נוכחות מרשימה.",
     "material":"כסף מצופה 925, גימור מלוטש","dim":"גובה 34 ס״מ","stock":2,"threshold":3,"status":"active","sold":6},
    {"id":13,"sku":"MEN-TCH-13","cat":"menorahs","catLabel":"חנוכיות","name":"חנוכיית תחרה חרוטה","price":495,"oldPrice":None,"badge":None,
     "short":"חנוכיה קומפקטית עם עיטורי תחרה מסולסלים וחריטה עברית על הבסיס.",
     "desc":"חנוכיה קומפקטית ואלגנטית בעלת זרועות עדינות בעיצוב תחרה מסולסלת, וחריטת טקסט עברי מסורתית על הבסיס. גודלה הנוח הופך אותה למתאימה גם לדירות קטנות וגם כמתנה מיוחדת.",
     "material":"כסף מצופה","dim":"גובה 16 ס״מ","stock":13,"threshold":5,"status":"active","sold":17},
    {"id":15,"sku":"GFT-KTR-15","cat":"gifts","catLabel":"מתנות","name":"מזוזת כתר מפוספסת","price":260,"oldPrice":None,"badge":"new",
     "short":"מזוזה כסופה בעיצוב עמודי פסים אנכיים, עם כתר מנוקב עשיר בראשה.",
     "desc":"מזוזה בקו נקי ומודרני, עשויה עמודי פסים אנכיים דקים המקנים תחושת תנועה, ובראשה כתר מנוקב עשיר בדוגמת פרחים. שילוב אלגנטי בין עיצוב עכשווי למוטיב מסורתי, ומגיעה עם תליון עיטורי בתחתית.",
     "material":"כסף מצופה מלוטש","dim":"גובה 20 ס״מ","stock":16,"threshold":6,"status":"active","sold":28},
    {"id":16,"sku":"GFT-PRH-16","cat":"gifts","catLabel":"מתנות","name":"מזוזת פרחים עתיקה","price":295,"oldPrice":None,"badge":None,
     "short":"מזוזה במסגרת פרחונית עשירה בסגנון עתיק, עם אות פתוחה במרכז.",
     "desc":"מזוזה במסגרת פרחונית מפוארת בסגנון וינטג', עם עיטורי פרחים ועלים המקיפים את הגוף ואות עברית פתוחה במרכז. מתנת בית קלאסית שמביאה נוכחות והדר לכל פתח.",
     "material":"כסף מצופה","dim":"גובה 11 ס״מ","stock":10,"threshold":6,"status":"draft","sold":4},
    {"id":17,"sku":"CND-SHS-17","cat":"candles","catLabel":"פמוטים","name":"מנורת שישה קנים","price":780,"oldPrice":None,"badge":"new",
     "short":"פמוט-מנורה כסוף בעל שישה קנים קמורים, למרכז שולחן חגיגי.",
     "desc":"מנורת הגשה כסופה בעלת שישה קנים קמורים הנפגשים בבסיס עגול ויציב. עיצוב עשיר ותנועתי שמעניק נוכחות רבה לשולחן החג, ומאיר את החלל בשילוב נרות רבים בו-זמנית.",
     "material":"כסף מצופה מלוטש","dim":"גובה 32 ס״מ","stock":4,"threshold":4,"status":"active","sold":9},
]

CATEGORIES = [
    {"id":"kiddush","label":"גביעי קידוש","status":"active","order":0},
    {"id":"candles","label":"פמוטים","status":"active","order":1},
    {"id":"menorahs","label":"חנוכיות","status":"active","order":2},
    {"id":"shabbat","label":"מוצרי שבת","status":"active","order":3},
    {"id":"havdalah","label":"הבדלה","status":"active","order":4},
    {"id":"gifts","label":"מתנות","status":"active","order":5},
    {"id":"silverware","label":"כלי כסף","status":"active","order":6},
]

CUSTOMERS = [
    {"id":"CU-201","name":"נועה כהן","email":"noa.cohen@example.com","phone":"050-1234567","orders":6,"spent":3420,"joined":"2024-11-03"},
    {"id":"CU-202","name":"איתמר לוי","email":"itamar.levi@example.com","phone":"052-2345678","orders":3,"spent":1180,"joined":"2025-01-17"},
    {"id":"CU-203","name":"שירה מזרחי","email":"shira.mizrahi@example.com","phone":"054-3456789","orders":9,"spent":5640,"joined":"2024-06-22"},
    {"id":"CU-204","name":"דניאל אברהם","email":"daniel.avraham@example.com","phone":"053-4567890","orders":1,"spent":420,"joined":"2025-07-02"},
    {"id":"CU-205","name":"מיכל בן דוד","email":"michal.bendavid@example.com","phone":"050-5678901","orders":4,"spent":2260,"joined":"2025-02-11"},
    {"id":"CU-206","name":"יוסף פרץ","email":"yosef.peretz@example.com","phone":"058-6789012","orders":12,"spent":8930,"joined":"2023-12-05"},
    {"id":"CU-207","name":"טליה גבאי","email":"talia.gabay@example.com","phone":"052-7890123","orders":2,"spent":790,"joined":"2025-05-19"},
    {"id":"CU-208","name":"רועי שרון","email":"roi.sharon@example.com","phone":"054-8901234","orders":7,"spent":4110,"joined":"2024-09-14"},
    {"id":"CU-209","name":"אביגיל נחום","email":"avigail.nachum@example.com","phone":"050-9012345","orders":5,"spent":2890,"joined":"2024-08-27"},
    {"id":"CU-210","name":"עמית רוזן","email":"amit.rozen@example.com","phone":"053-0123456","orders":2,"spent":640,"joined":"2025-06-30"},
    {"id":"CU-211","name":"הדר אשכנזי","email":"hadar.ashkenazi@example.com","phone":"058-1122334","orders":8,"spent":5320,"joined":"2024-04-10"},
    {"id":"CU-212","name":"ליאור שמעוני","email":"lior.shimoni@example.com","phone":"052-2233445","orders":1,"spent":265,"joined":"2025-08-01"},
]

PROMOTIONS = [
    {"id":"PR-01","name":"מבצע ראש השנה","code":"ROSHHASHANA25","discount":25,"start":"2026-08-20","end":"2026-09-10","status":"active"},
    {"id":"PR-02","name":"הנחת לקוחות חדשים","code":"WELCOME10","discount":10,"start":"2026-01-01","end":"2026-12-31","status":"active"},
    {"id":"PR-03","name":"מבצע חנוכה","code":"CHANUKAH26","discount":20,"start":"2026-11-25","end":"2026-12-20","status":"scheduled"},
    {"id":"PR-04","name":"משלוח חינם מעל 500 ₪","code":"FREESHIP500","discount":0,"start":"2026-06-01","end":"2026-12-31","status":"active"},
    {"id":"PR-05","name":"מבצע קיץ","code":"SUMMER26","discount":15,"start":"2026-06-01","end":"2026-08-15","status":"expired"},
    {"id":"PR-06","name":"מבצע יום האהבה","code":"LOVE26","discount":18,"start":"2027-02-05","end":"2027-02-15","status":"scheduled"},
]

STORE_INFO = {
    "id": "store_info",
    "name": "בראשית יודאיקה",
    "email": "info@bereshit-judaica.co.il",
    "phone": "03-1234567",
    "address": "רחוב יפו 22, ירושלים",
    "currency": "ILS",
    "description": "בית מלאכה לכלי כסף וטקס — יודאיקה איכותית בעבודת יד.",
}


def _pick(arr, i):
    return arr[i % len(arr)]


def build_orders():
    """Same generation logic as shared/mock-data.js's ORDERS, ported 1:1
    so the seeded orders line up with what the frontend used to show."""
    order_statuses = ["ממתין לאישור", "בטיפול", "נשלח", "נמסר", "בוטל"]
    pay_statuses = ["שולם", "ממתין לתשלום", "נכשל"]

    orders = []
    for i in range(16):
        cust = _pick(CUSTOMERS, i * 3 + 1)
        items_count = 1 + (i % 3)
        items = []
        for k in range(items_count):
            p = _pick(PRODUCTS, (i * 2 + k * 5 + 3))
            qty = 1 + ((i + k) % 2)
            items.append({"productId": p["id"], "name": p["name"], "cat": p["catLabel"], "price": p["price"], "qty": qty})
        total = sum(it["price"] * it["qty"] for it in items)
        status = _pick(order_statuses, i)
        pay = "נכשל" if status == "בוטל" else _pick(pay_statuses, i + 1)
        day = max(1, 24 - i)
        date = f"2026-08-{day:02d}"
        orders.append({
            "id": f"BJ-{10234 + i}",
            "customerId": cust["id"],
            "customer": {"id": cust["id"], "name": cust["name"], "email": cust["email"], "phone": cust["phone"]},
            "date": date,
            "items": items,
            "total": total,
            "status": status,
            "pay": pay,
            "shipping": {
                "address": "רחוב הרצל 14, תל אביב",
                "city": "תל אביב-יפו",
                "zip": "6423806",
                "method": "שליח עד הבית" if i % 3 == 0 else "איסוף עצמי מהחנות",
            },
            "payment": {
                "method": "PayPal" if i % 4 == 0 else f"כרטיס אשראי •••• {4000 + i}",
                "date": date,
            },
        })
    return orders


ORDERS = build_orders()
