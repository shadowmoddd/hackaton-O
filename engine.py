import re, random, os, json, datetime as dt
from data import DEST

MON = {"янв":1,"фев":2,"мар":3,"апр":4,"мая":5,"май":5,"июн":6,"июл":7,"авг":8,"сен":9,"окт":10,"ноя":11,"дек":12}
MNAME = ["","январе","феврале","марте","апреле","мае","июне","июле","августе","сентябре","октябре","ноябре","декабре"]
KINDS = {"cheap":"Выгодный","calm":"Спокойный","bold":"Смелый"}
NAMES = ["Palm Residence","Sea Breeze","Grand Azure","Coral Bay","Family Resort","Blue Lagoon","Olive Garden","Marina View"]

def fmt(h): return f"{int(h)%24:02d}:{int(h%1*60):02d}"

# ---------- 1. Trip State: понимание запроса ----------
def new_state():
    return dict(origin="Москва",adults=2,kids=0,dog=False,nights=7,budget=150000,month=None,
                max_flight=None,cheap=False,breakfast=False,date=None,explicit=[])

def llm_parse(text):
    """Опционально: LLM достаёт поля. Без ANTHROPIC_API_KEY возвращает {}."""
    if not os.getenv("ANTHROPIC_API_KEY"): return {}
    try:
        import anthropic
        r = anthropic.Anthropic().messages.create(model="claude-sonnet-4-6", max_tokens=300,
          system="Верни ТОЛЬКО JSON без пояснений с полями (опускай неизвестные): month(1-12), nights, budget(руб, int), adults, kids, dog(bool), max_flight(часы), cheap(bool), breakfast(bool).",
          messages=[{"role":"user","content":text}])
        return json.loads(r.content[0].text.strip().strip("`").replace("json","",1))
    except Exception: return {}

def parse(text, s=None):
    s = s or new_state(); t = text.lower(); ex = s["explicit"]
    def put(k,v):
        s[k]=v
        if k not in ex: ex.append(k)
    for k,v in MON.items():
        if re.search(r"\b"+k,t): put("month",v); break
    m = re.search(r"(\d[\d ]*)\s*(тыс|к\b|k\b)",t)
    if m: put("budget",int(m.group(1).replace(" ",""))*1000)
    else:
        m = re.search(r"\b(\d{5,7})\b",t)
        if m: put("budget",int(m.group(1)))
    m = re.search(r"(\d+)\s*(ноч|дн|сут)",t)
    if m: put("nights",int(m.group(1)))
    elif "недел" in t: put("nights",14 if re.search(r"(две|2) недел",t) else 7)
    elif "выходн" in t: put("nights",3)
    m = re.search(r"(\d)\s*(детей|дет|ребен|ребён)",t)
    if m: put("kids",int(m.group(1)))
    elif re.search(r"ребен|ребён|дет(ьми|ям|и)",t): put("kids",1)
    if re.search(r"вдвоем|вдвоём",t): put("adults",2)
    if re.search(r"\bодин\b|\bодна\b|соло",t): put("adults",1)
    if re.search(r"собак|пёс|\bпес\b",t): put("dog",True)
    if re.search(r"недорог|дёшево|дешево|бюджетн|эконом",t): put("cheap",True)
    if re.search(r"завтрак",t): put("breakfast",True)
    m = re.search(r"не более (\d+) час",t)
    if m: put("max_flight",int(m.group(1)))
    elif re.search(r"без долг\w* перел|недалеко|близк",t): put("max_flight",5)
    for k,v in llm_parse(text).items():
        if k in s and v is not None: put(k,v)
    today = dt.date.today()
    if not s["month"]: s["month"] = today.month % 12 + 1
    y = today.year if (s["month"],10) >= (today.month,today.day) else today.year+1
    if not s["date"] or "month" in ex: s["date"] = dt.date(y,s["month"],10).isoformat()
    return s

def assumptions(s):
    d = dict(month="месяц — следующий",nights=f"{s['nights']} ночей",budget=f"бюджет до {s['budget']:,} ₽".replace(","," "),
             adults=f"{s['adults']} взрослых",origin="вылет из Москвы")
    return [v for k,v in d.items() if k not in s["explicit"]]

# ---------- 2. Мок-данные (детерминированные от даты) ----------
def hotels(d, date):
    r = random.Random(d["name"]+str(date.month)); out=[]
    for n in r.sample(NAMES,6):
        st = r.choice([3,4,4,5,5]); k = {3:.6,4:1,5:1.8}[st]
        price = int(d["base"]*k*r.uniform(.85,1.2)*(1+(date.toordinal()%7)/60)/100)*100
        out.append(dict(name=f"{n} {st}★",stars=st,price=price,beach=r.choice([50,150,300,800,1500]),
            free_cancel=r.random()<.55,breakfast=r.random()<.6,kids=r.random()<.5 or n=="Family Resort",
            pets=r.random()<.25,rating=round(r.uniform(7.6,9.6),1)))
    return out

def flights(d, date):
    r = random.Random(d["name"]+str(date.toordinal())); out=[]
    for dep in (1.5,7.0,12.0,17.5):
        arr = (dep+d["fh"]+d["tz"])%24
        out.append(dict(dep=dep,arr=round(arr,1),dep_s=fmt(dep),arr_s=fmt(arr),
            price=int(d["fh"]*3800*r.uniform(.8,1.5)/100)*100+9000,refundable=r.random()<.35,
            ret=r.choice([9.0,14.0,23.5])))
    return out

def mk(s,h,f):
    people = s["adults"]+.75*s["kids"]
    return dict(hotel=h,flight=f,base=int(f["price"]*people+h["price"]*s["nights"]),extras=[],total=0)

def retotal(p): p["total"]=p["base"]+sum(e["price"] for e in p["extras"]); return p

def dest_by_name(n): return next(d for d in DEST if d["name"]==n)

def combos(s,d):
    date = dt.date.fromisoformat(s["date"])
    return [retotal(mk(s,h,f)) for h in hotels(d,date) for f in flights(d,date)]

# ---------- 3. Выбор направления: числа считает код ----------
def rank(s):
    date = dt.date.fromisoformat(s["date"]); out=[]
    w = (.3,.3,.4) if s["kids"] else (.3,.5,.2) if s["cheap"] else (.4,.35,.25)
    for d in DEST:
        if s["max_flight"] and d["fh"]>s["max_flight"]: continue
        temp = d["t"][date.month-1]; est = min(p["total"] for p in combos(s,d))
        sw = max(0,1-abs(temp-28)/12); sb = 1 if est<=s["budget"] else max(0,1-(est-s["budget"])/s["budget"])
        sf = max(0,1-d["fh"]/10); sc = w[0]*sw+w[1]*sb+w[2]*sf-(0.03 if d["visa"]!="нет" else 0)
        out.append(dict(name=d["name"],country=d["country"],temp=temp,fh=d["fh"],visa=d["visa"],est=est,
            score=round(sc*100),why=f"{temp}°C в {MNAME[date.month]}, перелёт ~{d['fh']} ч, от {est:,} ₽ на всех ({'в бюджете' if est<=s['budget'] else 'выше бюджета'}), виза: {d['visa']}".replace(","," ")))
    return sorted(out,key=lambda x:-x["score"])[:3]

# ---------- 4. Три точки Парето с ценой выбора ----------
def packages(s,d):
    P = combos(s,d)
    ok = [p for p in P if (not s["dog"] or p["hotel"]["pets"]) and (not s["breakfast"] or p["hotel"]["breakfast"])]
    if len(ok)<3: ok = P
    cheap = min(ok,key=lambda p:p["total"]); rest=[p for p in ok if p is not cheap]
    def calm_sc(p):
        h,f=p["hotel"],p["flight"]
        return 3*h["free_cancel"]+2*f["refundable"]+(h["beach"]<=300)+(s["kids"] and h["kids"])+2*(9<=f["arr"]<=20)-p["total"]/s["budget"]
    calm = max(rest,key=calm_sc); rest.remove(calm)
    bold = max(rest,key=lambda p:p["hotel"]["rating"]*10+p["hotel"]["stars"]-30*max(0,p["total"]/(s["budget"]*1.15)-1))
    res = dict(cheap=cheap,calm=calm,bold=bold)
    for k,p in res.items(): explain(s,p,k,cheap)
    return res

def explain(s,p,kind,cheap):
    h=p["hotel"]; f=p["flight"]
    p["kind"]=kind; p["label"]=KINDS[kind]
    p["why"]=[f"{h['name']}: рейтинг {h['rating']}, до пляжа {h['beach']} м",
              f"Перелёт {f['dep_s']} → {f['arr_s']}, "+("с возвратом" if f["refundable"] else "невозвратный")]
    sac=[]
    if kind!="cheap": sac.append(f"+{p['total']-cheap['total']:,} ₽ к самому дешёвому".replace(","," "))
    if not h["free_cancel"]: sac.append("нет бесплатной отмены отеля")
    if not h["breakfast"]: sac.append("без завтрака")
    p["sacrifice"]=sac or ["ничем существенным"]
    p["issues"]=validate(s,p)
    return p

# ---------- 5. ВАЛИДАТОР СОСТЫКОВОК (детерминированный) ----------
def has(p,c): return any(e["code"]==c for e in p["extras"])

def validate(s,p):
    h,f,I = p["hotel"],p["flight"],[]
    def add(code,sev,msg,fix): I.append(dict(code=code,sev=sev,msg=msg,fix=fix))
    if 5<=f["arr"]<13 and not has(p,"early"):
        add("early","mid",f"Прилёт в {f['arr_s']}, заселение с 14:00 — ждать {int(14-f['arr'])} ч","Ранний заезд (+50% ночи)")
    if (f["arr"]>=23 or f["arr"]<5):
        add("day_flight","high" if s["kids"] else "mid",f"Ночной прилёт ({f['arr_s']})"+(" с ребёнком" if s["kids"] else "")+": трансфер и заселение под вопросом","Заменить на дневной рейс")
    if h["free_cancel"] and not f["refundable"]:
        add("refund_flight","mid","Отель с бесплатной отменой, но билет невозвратный: при отмене потеряете перелёт","Взять возвратный билет")
    if f["ret"]-12>=8 and not has(p,"late"):
        add("late","low",f"Обратный рейс в {fmt(f['ret'])}, выселение в 12:00 — {int(f['ret']-12)} ч без номера","Поздний выезд (+50% ночи)")
    if p["total"]>s["budget"]:
        add("cheapest","high",f"Итого {p['total']:,} ₽ — выше бюджета на {p['total']-s['budget']:,} ₽".replace(","," "),"Перейти на самый дешёвый вариант")
    if s["dog"] and not h["pets"]:
        add("pet_hotel","high","Отель не принимает с животными","Подобрать отель pet-friendly")
    if s["breakfast"] and not h["breakfast"]:
        add("pet_hotel" if False else "bf_hotel","mid","Завтрак не включён","Отель с завтраком")
    return I

def apply_fix(s,p,d,code):
    date=dt.date.fromisoformat(s["date"]); H=hotels(d,date); F=flights(d,date); h,f=p["hotel"],p["flight"]
    if code in("early","late"):
        p["extras"].append(dict(code=code,name="Ранний заезд" if code=="early" else "Поздний выезд",price=h["price"]//2))
    elif code=="day_flight": f=min([x for x in F if 8<=x["arr"]<=21] or F,key=lambda x:x["price"])
    elif code=="refund_flight": f=min([x for x in F if x["refundable"]] or F,key=lambda x:x["price"])
    elif code=="pet_hotel": h=min([x for x in H if x["pets"]] or H,key=lambda x:x["price"])
    elif code=="bf_hotel": h=min([x for x in H if x["breakfast"]] or H,key=lambda x:x["price"])
    elif code=="cheapest":
        c=min(combos(s,d),key=lambda x:x["total"]); h,f=c["hotel"],c["flight"]
    ext=p["extras"]; p.update(mk(s,h,f)); p["extras"]=ext; retotal(p)
    p["issues"]=validate(s,p); return p

# ---------- 6. Пересборка с diff ----------
NUM={"два":"2","три":"3","пять":"5","неделю":"7","день":"1"}

def patch(s,text):
    s=json.loads(json.dumps(s)); t=text.lower(); ch=[]
    for w,n in NUM.items(): t=t.replace(w,n)
    m=re.search(r"на (\d+)\D{0,6}(позже|раньше)",t)
    if m:
        k=int(m.group(1))*(1 if m.group(2)=="позже" else -1)
        s["date"]=(dt.date.fromisoformat(s["date"])+dt.timedelta(days=k)).isoformat(); ch.append(f"даты сдвинуты на {k:+d} дн.")
    m=re.search(r"бюджет\D{0,15}(\d+)\s*(тыс|к)?",t)
    if m: s["budget"]=int(m.group(1))*(1000 if m.group(2) or int(m.group(1))<10000 else 1); ch.append(f"бюджет {s['budget']:,} ₽".replace(","," "))
    elif "бюджет" in t and "меньше" in t: s["budget"]=int(s["budget"]*.8); ch.append("бюджет −20%")
    if re.search(r"собак|пёс",t): s["dog"]=True; ch.append("едет собака")
    if "завтрак" in t: s["breakfast"]=True; ch.append("нужен завтрак")
    m=re.search(r"(\d+)\s*ноч",t)
    if m: s["nights"]=int(m.group(1)); ch.append(f"{s['nights']} ночей")
    return s,ch

def snap(p):
    h,f=p["hotel"],p["flight"]
    return {"Отель":h["name"],"Цена ночи":h["price"],"Завтрак":"да" if h["breakfast"] else "нет","Перелёт туда":f"{f['dep_s']}→{f['arr_s']}",
            "Билет":f["price"],"Возврат билета":"да" if f["refundable"] else "нет","Итого":p["total"],"Проблем":len(p["issues"])}

def replan(s,p,d,text):
    s2,ch=patch(s,text); new=packages(s2,d)[p["kind"]]
    a,b=snap(p),snap(new)
    diff=[dict(what=k,old=a[k],new=b[k]) for k in a if a[k]!=b[k]]
    return s2,new,ch,diff
