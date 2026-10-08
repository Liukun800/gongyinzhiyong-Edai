"""Create evidence-grounded, editable blue diagrams for Word body text."""
import json
import math
from pathlib import Path
from xml.etree import ElementTree as E

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '评审整改交付版/图文增强与痛点完善_20261008'
ASSETS = OUT / '蓝色矢量图'
S = 'http://www.w3.org/2000/svg'
E.register_namespace('', S)
BLUE = '#236BB0'
DEEP = '#174B78'
LIGHT = '#EAF3FB'
MID = '#6C9BC5'
INK = '#23465F'
GRAY = '#59758A'
LINE = '#BDD3E6'

class Canvas:
    def __init__(self, key, title, height):
        self.key, self.title, self.height = key, title, height
        self.root = E.Element('{'+S+'}svg', {'viewBox': f'0 0 1500 {height}', 'width': '1500', 'height': str(height), 'role': 'img'})
        E.SubElement(self.root, '{'+S+'}title').text = title
        defs = E.SubElement(self.root, '{'+S+'}defs')
        for name, stops in [('panel', [('0%', '#FFFFFF'), ('100%', '#DDEDFB')]),
                            ('blue', [('0%', '#519CE0'), ('55%', BLUE), ('100%', DEEP)]),
                            ('deep', [('0%', '#387CB6'), ('100%', '#123E69')]),
                            ('pale', [('0%', '#F6FBFF'), ('100%', '#AFCFEB')])]:
            grad=E.SubElement(defs,'{'+S+'}linearGradient',{'id':name,'x1':'0','y1':'0','x2':'0.85','y2':'1'})
            for offset,color in stops:E.SubElement(grad,'{'+S+'}stop',{'offset':offset,'stop-color':color})
        shadow=E.SubElement(defs,'{'+S+'}filter',{'id':'shadow','x':'-15%','y':'-20%','width':'140%','height':'150%'})
        E.SubElement(shadow,'{'+S+'}feDropShadow',{'dx':'0','dy':'5','stdDeviation':'5','flood-color':'#235A87','flood-opacity':'0.13'})
        marker = E.SubElement(defs, '{'+S+'}marker', {'id': 'arrow', 'viewBox': '0 0 10 10', 'refX': '9', 'refY': '5', 'markerWidth': '7', 'markerHeight': '7', 'orient': 'auto-start-reverse'})
        E.SubElement(marker, '{'+S+'}path', {'d': 'M 0 0 L 10 5 L 0 10 z', 'fill': BLUE})
        self.rect(0, 0, 1500, height, '#FFFFFF', stroke='none')

    def el(self, tag, **attrs):
        return E.SubElement(self.root, '{'+S+'}'+tag, {k.replace('_','-'):str(v) for k,v in attrs.items()})

    def rect(self,x,y,w,h,fill=LIGHT,stroke=LINE,rx=6):
        return self.el('rect',x=x,y=y,width=w,height=h,fill=fill,stroke=stroke,stroke_width=2,rx=rx)

    def text(self,x,y,value,size=30,color=INK,bold=False,anchor='start',width=1400):
        n=self.el('text',x=x,y=y,fill=color,font_family='Microsoft YaHei, SimHei, sans-serif',font_size=size,font_weight='700' if bold else '400',text_anchor=anchor)
        n.set('data-fit-width',str(width))
        n.text=value
        return n

    def lines(self,x,y,lines,size=29,color=INK,anchor='start',width=420,step=43):
        for i,t in enumerate(lines): self.text(x,y+i*step,t,size,color,anchor=anchor,width=width)

    def arrow(self,x1,y1,x2,y2,dash=False):
        n=self.el('path',d=f'M{x1},{y1} L{x2},{y2}',fill='none',stroke=BLUE,stroke_width=3,marker_end='url(#arrow)')
        if dash:n.set('stroke-dasharray','8 7')

    def box(self,x,y,w,h,title,lines,fill=LIGHT,header=BLUE,size=29):
        self.rect(x+7,y+9,w,h,'#CEDFEF',stroke='none',rx=8)
        self.rect(x,y,w,h,'url(#panel)' if fill==LIGHT else fill,rx=8)
        self.rect(x,y,w,55,'url(#deep)' if header==DEEP else 'url(#blue)',stroke='none',rx=8)
        self.el('path',d=f'M{x+12},{y+2} H{x+w-12}',stroke='#9DC8EC',stroke_width=2,opacity='.7')
        self.text(x+w/2,y+38,title,31,'white',True,'middle',w-24)
        self.lines(x+22,y+96,lines,size,width=w-44)

    def band(self,y,title,fill=DEEP):
        self.rect(44,y+5,1420,58,'#CFDFEE',stroke='none')
        self.rect(40,y,1420,58,'url(#deep)' if fill==DEEP else fill,stroke='none')
        self.text(750,y+39,title,31,'white',True,'middle',1370)

    def plate(self,x,y,w,h):
        self.el('polygon',points=f'{x},{y} {x+22},{y-14} {x+w+22},{y-14} {x+w},{y}',fill='#9CC2E5')
        self.el('polygon',points=f'{x+w},{y} {x+w+22},{y-14} {x+w+22},{y+h-14} {x+w},{y+h}',fill='#ADC9E1')
        return self.rect(x,y,w,h,'url(#panel)',rx=5)

    def podium(self,x,y,w,label):
        self.el('ellipse',cx=x+w/2,cy=y+57,rx=w/2+12,ry=23,fill='#D5E4F0',opacity='.5')
        self.rect(x,y,w,52,'url(#deep)',stroke='none',rx=4)
        self.el('ellipse',cx=x+w/2,cy=y,rx=w/2,ry=17,fill='url(#pale)',stroke=LINE,stroke_width=2)
        self.el('path',d=f'M{x+5},{y+16} Q{x+w/2},{y+46} {x+w-5},{y+16}',fill='none',stroke='#7EABD2',stroke_width=2)
        self.text(x+w/2,y+45,label,29,'white',True,'middle',w-24)

    def note(self,y,title):
        self.text(750,y,title,27,GRAY,anchor='middle',width=1430)

    def save(self):
        # Word ignores some filtered SVG objects; explicit backing shapes carry depth.
        for node in self.root.iter():node.attrib.pop('filter',None)
        path=ASSETS/(self.key+'.svg')
        path.write_bytes(E.tostring(self.root,encoding='utf-8',xml_declaration=True))
        return {'key':self.key,'title':self.title,'svg':str(path),'png':str(path.with_suffix('.png')),'width':1500,'height':self.height}

def main():
    ASSETS.mkdir(parents=True,exist_ok=True)
    figures=[]
    c=Canvas('overview','项目全局总览与前置核验位置',525)
    c.band(12,'材料归集后、综合审查前  用途一致性与经营陈述矛盾核验')
    c.box(40,105,440,225,'规则与材料条件',['输入完整性与可比口径','主体、期间和有效版本','客观缺件交经办补齐'])
    c.box(530,105,440,225,'System 1  Jev快判断',['对限定问题选择候选','结果、分数与来源留存','工作台关联成对原文'],header=DEEP)
    c.box(1020,105,440,225,'System 2  按需协同',['围绕复杂未决关系分析','拟协同工银智涌能力','检查返回依据再交人员'])
    c.arrow(488,217,520,217);c.arrow(978,217,1010,217)
    c.text(995,96,'复杂未决时升级',24,DEEP,True,'middle',230)
    c.arrow(750,337,750,357)
    c.band(365,'人员承接  补件、核实与纠正 → 核验事项包 → 后续综合审查')
    c.note(462,'共同约束  原文引用、材料版本、未决事项与人员处理记录')
    c.note(507,'价值评价  关键错误、查证工时、处理响应与完整成本')
    figures.append(c.save())
    c=Canvas('policy','政策脉络与贷前核验设计响应',540)
    c.el('path',d='M100,83 H1400',stroke='#A8C9E6',stroke_width=14,stroke_linecap='round')
    for x,date in [(260,'2023年10月'),(750,'2024年12月'),(1240,'2026年9月')]:
        c.el('circle',cx=x,cy=83,r=19,fill='url(#blue)',stroke='white',stroke_width=5)
        c.text(x,43,date,31,DEEP,True,'middle',400)
        c.el('line',x1=x,y1=106,x2=x,y2=132,stroke=BLUE,stroke_width=3)
    c.box(40,132,440,200,'普惠金融提质增效',['国发〔2023〕15号','推进数字普惠金融','服务实体与风险管理并重'])
    c.box(530,132,440,200,'数据安全全过程管理',['金规〔2024〕24号','分类分级与授权访问','委托处理与风险处置'],header=DEEP)
    c.box(1020,132,440,200,'智能应用价值评价',['金融时报行业报道','平衡算力投入与产出','关注实际工作效能'])
    for x in [260,750,1240]:c.arrow(x,346,x,373)
    for x,title,detail in [(40,'效率响应','限定任务，减少重复判读'),(530,'治理响应','原文、权限与版本关联'),(1020,'评价响应','核验质量、工时与成本')]:
        c.plate(x,389,420,90)
        c.text(x+210,425,title,31,DEEP,True,'middle',385)
        c.text(x+210,466,detail,28,INK,anchor='middle',width=385)
    c.note(527,'时间轴涵盖公开政策与行业报道；下层对应本项目的设计响应。')
    figures.append(c.save())

    c=Canvas('ecology','工行信贷生态与前置核验协同',485)
    c.band(15,'工银智涌能力体系与智贷通融资业务场景')
    c.box(40,115,425,235,'材料归集与经办处理',['归集申请及经营材料','检查主体、期间与口径','承接补件与经营核实'])
    c.box(535,115,425,235,'本项目前置核验组件',['用途一致性与经营矛盾','Jev有限候选判断','成对原文与待处理事项'],header=DEEP)
    c.box(1030,115,425,235,'工小审相关评审任务',['辅助核对材料与疑点','按需协同复杂分析','人员形成综合评审意见'])
    c.arrow(475,235,522,235);c.arrow(970,235,1017,235)
    c.rect(40,380,1420,62)
    c.text(750,422,'协同边界  材料归集后接收任务，综合审查前交付核验事项包',30,INK,True,'middle',1380)
    c.note(478,'银行系统定位依据公开披露；组件关系为拟议业务设计。')
    figures.append(c.save())

    evidence=json.loads((OUT/'评审补证材料/补证核查.json').read_text(encoding='utf-8'))
    paired=evidence['paired_dual']
    c=Canvas('paired','历史双系统升级任务的配对结果',535)
    c.band(15,'28份自编仿真  社区快判断＋Qwen2.5-0.5B实验协同')
    c.text(400,119,'7份升级任务的实际变化',33,DEEP,True,'middle',670)
    c.text(1140,119,'同一批材料的总体结果',33,DEEP,True,'middle',610)
    cats=[('纠错','纠错'),('新增错误','新增错误'),('正确保持','正确保持'),('错误保持','错误保持')]
    for i,(key,title) in enumerate(cats):
        x=45+(i%2)*375;y=150+(i//2)*130
        c.plate(x,y,325,106)
        c.text(x+22,y+39,title,29,INK,True,width=280)
        c.text(x+300,y+88,str(len(paired['buckets'][key]))+'份',37,BLUE,True,'end',260)
    c.el('line',x1=820,y1=128,x2=820,y2=406,stroke=LINE,stroke_width=2)
    for y,title,n,color in [(164,'快判断',paired['fast_correct'],BLUE),(264,'双系统',paired['final_correct'],DEEP)]:
        c.text(880,y+26,title,29,INK,True,width=220)
        c.rect(880,y+42,540,35,'#E6EFF7',stroke='none')
        c.rect(880,y+42,540*n/28,35,'url(#blue)' if color==BLUE else 'url(#deep)',stroke='none')
        c.text(1420,y+26,f'{n}/28',35,color,True,'end',220)
    c.text(1150,391,'参考一致数净变化  −2份',31,DEEP,True,'middle',580)
    c.note(454,'H03、H09新增错误；H05未纠正。未升级路径仍保留10份错误。')
    c.note(505,'标签未独立业务复核；本次配对重算不代表官方Jev或工银智涌的任务效果。')
    figures.append(c.save())

    c=Canvas('pain','行业要求向材料核验痛点的转化',715)
    headers=[(40,420,'公开依据'),(500,500,'材料评审中的问题'),(1040,420,'产品响应')]
    for x,w,t in headers:c.rect(x,18,w,58,DEEP,DEEP);c.text(x+w/2,57,t,32,'white',True,'middle',w-20)
    rows=[
        (['信息获取与服务成本','普惠金融行业报道'],['材料分散、比较口径不齐','缺件与事实冲突容易混淆'],['核对主体、期间与范围','客观缺件先补充材料']),
        (['数字化服务与风险管理','普惠金融政策'],['同义改写与局部事实差异','增加重复翻找与判读工作'],['限定问题与有限候选','关联成对原文供人员核实']),
        (['全过程安全管理','数据安全管理办法'],['版本更新后依据需同步','责任与未决事项需承接'],['版本绑定与复核留痕','事项包随材料流转']),
        (['算力投入与价值产出','银行AI行业报道'],['不同难度任务如何配置能力','需同时核算资源与人员工时'],['规则、快判断与按需分析','同质量下测量完整收益']),
    ]
    for i,(a,b,d) in enumerate(rows):
        y=98+i*132
        for x,w,lines in [(40,420,a),(500,500,b),(1040,420,d)]:
            c.rect(x,y,w,114,'#F5F9FD' if i%2==0 else LIGHT)
            c.lines(x+20,y+44,lines,29,width=w-40,step=40)
        c.arrow(467,y+57,491,y+57);c.arrow(1007,y+57,1031,y+57)
    c.note(675,'材料评审问题为据公开背景归纳的场景分析，具体任务量与耗时在业务评价中确认。')
    figures.append(c.save())

    c=Canvas('value','首期切入与价值验证链条',420)
    titles=['材料关系核验','证据与事项组织','人员核实与交接','业务增量评价']
    lines=[['资金用途一致性','经营陈述矛盾'],['限定建议与成对原文','缺件与未决事项'],['按缺项补件或核实','确认、更正并流转'],['关键错误与查证工时','响应与完整成本']]
    for i in range(4):
        x=40+i*365;c.box(x,50,325,200,titles[i],lines[i],header=DEEP if i==0 else BLUE)
        if i<3:c.arrow(x+335,150,x+353,150)
    c.band(300,'验证对象为单项材料核验及结果交接，授信决策沿用既有授权流程')
    c.note(405,'价值评价覆盖材料核验与事项交接，具体收益依据同任务业务记录。')
    figures.append(c.save())

    c=Canvas('scope','目标业务与首期服务范围',445)
    c.box(40,30,440,300,'业务入口',['小微经营贷款材料评审','申请说明、订单或合同','经营陈述与补充说明','借款人沿用既有申请渠道'])
    c.box(530,30,440,300,'首期服务单元',['一项任务对应一组材料','用途与资金归属比较','可比经营事实比较','输出限定核验建议'])
    c.box(1020,30,440,300,'处理结果去向',['经办补齐缺项','审查核实原文与疑点','管理人员追踪状态','后续综合审查承接事项'])
    c.arrow(488,180,520,180);c.arrow(978,180,1010,180)
    c.note(394,'面向材料评审岗位提供辅助核验服务；首期输入为已整理文本。')
    figures.append(c.save())

    c=Canvas('use','人员操作与价值观察点',425)
    c.box(40,35,440,235,'材料经办',['看到缺项与可比口径','补齐后重跑相关任务','观察  补件往返次数'])
    c.box(530,35,440,235,'审查复核',['同屏核对成对原文','确认、更正或继续查证','观察  查证与纠正工时'])
    c.box(1020,35,440,235,'业务与技术管理',['追踪未决事项与版本','确认交接与异常承接','观察  遗漏与运行开销'])
    c.band(320,'同一申请绑定材料版本、核验任务和人员处理记录')
    c.note(416,'业务观察以补件、原文查证和未决事项交接的实际操作记录为依据。')
    figures.append(c.save())

    c=Canvas('runtime','原型运行模式与共同业务闭环',470)
    c.box(40,30,440,215,'流程演示',['独立仿真数据库','预设结论用于操作展示','展示与模型实测分别标识'])
    c.box(530,30,440,215,'社区研究模式',['本地快判断真实推理','慢分析为实验协同','记录模型与材料版本'])
    c.box(1020,30,440,215,'官方Jev模式',['独立官方判断服务入口','返回答案与用量留存','失败或达到上限转人员'])
    for x in [260,750,1240]:c.arrow(x,255,x,292)
    c.band(305,'共同闭环  材料提交 → 核验建议 → 原文查证 → 人员处理 → 事项交接')
    c.note(419,'各模式均留存材料版本、模型来源及人员处理记录。')
    figures.append(c.save())

    c=Canvas('route','不确定事项的原因与承接方式',530)
    rows=[('事实尚缺',['订单缺失或口径不清'],['经办补件或核实输入','形成新版本后再核验']),
          ('明确矛盾',['存在可比的相斥原文'],['人员核实事实与原因','保留疑点及处置依据']),
          ('关系复杂',['材料充分但需要多步分析'],['围绕未决问题按需分析','检查返回依据再交人员']),
          ('运行异常',['调用失败或记录不可写'],['保留失败并暂停采用建议','恢复原处理流程'])]
    for i,(title,a,b) in enumerate(rows):
        y=25+i*112
        c.rect(40,y,265,92,DEEP,DEEP);c.text(172,y+59,title,32,'white',True,'middle',225)
        c.rect(345,y,560,92);c.lines(365,y+55,a,30,width=520)
        c.rect(965,y,495,92);c.lines(985,y+36,b,28,width=455,step=37)
        c.arrow(313,y+46,335,y+46);c.arrow(913,y+46,953,y+46)
    c.note(509,'路由依据是材料条件与问题性质；模型分数单独用于判断不确定性评价。')
    figures.append(c.save())

    c=Canvas('version','领域迭代与版本验证闭环',455)
    c.el('ellipse',cx=750,cy=244,rx=221,ry=179,fill='#EAF4FC')
    c.el('circle',cx=750,cy=212,r=160,fill='none',stroke='#D0E2F2',stroke_width=38)
    for start,end in [(-134,-47),(-44,43),(46,133),(136,223)]:
        a,b=math.radians(start),math.radians(end)
        c.el('path',d=f'M{750+160*math.cos(a)},{212+160*math.sin(a)} A160,160 0 0 1 {750+160*math.cos(b)},{212+160*math.sin(b)}',fill='none',stroke=BLUE,stroke_width=6,marker_end='url(#arrow)')
    c.el('circle',cx=750,cy=212,r=104,fill='url(#panel)',stroke='#A9C9E5',stroke_width=2,filter='url(#shadow)')
    c.text(750,204,'领域适配',34,DEEP,True,'middle',185)
    c.text(750,250,'版本验证',31,INK,anchor='middle',width=185)
    for x,y,title,lines,num in [(40,25,'01 登记错误与原文',['区分漏识别与误报','记录材料、标签与模型'],'01'),
                              (1040,25,'02 提出适配候选',['调整任务或领域模型','保留旧版与修改依据'],'02'),
                              (1040,240,'03 开发回归与对照',['检查纠错及新增错误','复跑受影响方案'],'03'),
                              (40,240,'04 冻结独立评价',['采用新的未见资料','分别报告质量与成本'],'04')]:
        c.box(x,y,420,155,title,lines,size=28)
        inner=485 if x==40 else 1015
        target=630 if x==40 else 870
        level=100 if y==25 else 326
        c.el('line',x1=inner,y1=level,x2=target,y2=level,stroke=LINE,stroke_width=3)
    c.note(446,'评价未达要求时回到候选开发；开发资料与独立评价资料分别管理。')
    figures.append(c.save())

    c=Canvas('adoption','模型采用的分层判断依据',500)
    c.box(40,30,440,305,'核验质量门槛',['独立标签与新资料评价','关键矛盾漏检与误报','不可比识别与原文支持','未达要求  保持人员承接'])
    c.box(530,30,440,305,'协同增量评价',['慢分析是否成功纠错','是否引入新的错误','未决事项是否有效承接','无增益  调整协同范围'])
    c.box(1020,30,440,305,'完整收益评价',['新增判断与维护开销','查证、纠正及补件工时','同质量下的响应与费用','不划算  替换或限用'])
    c.arrow(488,175,520,175);c.arrow(978,175,1010,175)
    c.band(380,'按任务选择模型与采用范围，选择依据为业务增量')
    c.note(480,'三项共同验收后确定有限辅助使用范围。')
    figures.append(c.save())

    c=Canvas('time','完整核验路径的工时与时延测量',500)
    c.band(15,'同材料、同任务、同质量要求下记录全过程')
    labels=['材料准备','规则与判断','疑点处置','事项交接']
    lines=[['归集、解析与口径核对','记录材料版本'],['排队、推理与异常','记录两层调用用量'],['查证、补件与人员纠正','记录有效操作工时'],['复核摘要与未决事项','记录遗漏及返工']]
    for i in range(4):
        x=40+i*365;c.box(x,115,325,205,labels[i],lines[i],size=27)
        if i<3:c.arrow(x+334,213,x+355,213)
    c.rect(40,360,1420,88)
    c.text(750,393,'系统响应  请求发起至完整结构化返回',29,INK,True,'middle',1370)
    c.text(750,430,'人员操作与外部等待分别计量，不以调用次数替代业务效率',29,INK,anchor='middle',width=1370)
    figures.append(c.save())

    c=Canvas('cost','分层处理的完整成本构成',480)
    c.box(40,25,690,270,'对照路径完整成本',['共同材料准备与规则处理','生成模型的实际调用开销','人员复核、补件及纠正','部署、监控与维护分摊'])
    c.box(770,25,690,270,'分层路径完整成本',['相同材料准备与规则处理','快判断＋按需慢分析开销','人员复核、补件及纠正','路由、部署与维护分摊'],header=DEEP)
    c.band(340,'净节约 = 对照路径完整成本 − 分层路径完整成本')
    c.note(452,'仅在质量与人员负担满足要求时评价净节约，实际用量与计价条件共同记录。')
    figures.append(c.save())

    c=Canvas('deliver','银行适配交付内容与承接关系',610)
    c.el('ellipse',cx=750,cy=502,rx=454,ry=76,fill='#ECF5FC')
    c.el('path',d='M750,500 C720,370 595,388 570,294 M750,445 C790,337 933,355 940,269 M750,418 C710,336 750,277 750,234',fill='none',stroke='#377BB3',stroke_width=19,stroke_linecap='round')
    c.box(40,35,440,285,'业务与任务材料',['两项任务的口径与候选','材料范围与原文要求','人员动作与未决事项','工小审事项映射说明'])
    c.box(530,10,440,230,'技术与原型组件',['可替换判断服务','版本化事项包与接口','工作台与复核记录','异常、审计与恢复设计'],size=28,header=DEEP)
    c.box(1020,35,440,285,'验证与维护记录',['同任务逐例对照结果','模型与配置版本档案','质量、工时及成本评价','使用范围与更新验收'])
    c.el('path',d='M260,330 C260,390 500,338 572,379 M1240,330 C1240,390 1000,338 929,379',fill='none',stroke=BLUE,stroke_width=4)
    for x,label in [(590,'业务'),(750,'数据'),(910,'技术')]:
        c.el('circle',cx=x,cy=441,r=50,fill='url(#pale)',stroke='#A1C4E3',stroke_width=2,filter='url(#shadow)')
        c.text(x,451,label,30,DEEP,True,'middle',90)
    c.podium(460,510,580,'银行适配交付与共同验收')
    c.note(603,'以获准任务为交付单位，任务口径、环境权限与核验质量共同确认。')
    figures.append(c.save())

    c=Canvas('access','数据处理授权与责任边界',490)
    c.box(40,25,440,285,'材料进入前',['业务方确认任务范围','数据方确认来源与授权','明确模型服务与部署环境','按最小必要范围组织输入'])
    c.box(530,25,440,285,'材料处理时',['按岗位权限访问原文','绑定材料与模型版本','引用、运行和人员动作留痕','材料指令不改变系统权限'])
    c.box(1020,25,440,285,'结果交接后',['人员承接建议与疑点','按制度留存与恢复','异常时停止相关处理','复核后按范围恢复服务'])
    c.arrow(488,162,520,162);c.arrow(978,162,1010,162)
    c.band(365,'官方API实验使用自编仿真文本，客户资料按银行获准环境处理')
    c.note(470,'设计依据为数据安全管理要求，不能以服务可调用替代业务数据授权。')
    figures.append(c.save())

    c=Canvas('recovery','异常停止与业务恢复闭环',430)
    titles=['发现触发条件','停止相关任务','承接与定位','验证后恢复']
    lines=[['越权或依据不可追溯','关键错误超过约定上限'],['暂停采用相关建议','原业务处理持续运行'],['保留已有记录与待办','责任方核实并修复'],['完成回归与责任确认','按获准范围恢复']]
    for i in range(4):
        x=40+i*365;c.box(x,40,325,220,titles[i],lines[i],size=27)
        if i<3:c.arrow(x+334,150,x+355,150)
    c.band(310,'停止的是受影响组件任务，材料、历史结果与人员承接记录保留')
    c.note(409,'新增任务与模型版本分别验收，持续监测适用范围。')
    figures.append(c.save())

    c=Canvas('gantt','分阶段实施标准甘特图',700)
    left,right,top,row=415,1425,130,87
    unit=(right-left)/14
    c.text(45,62,'阶段与重点交付',32,INK,True,width=365)
    c.text((left+right)/2,62,'相对启动月  M0—M14',32,INK,True,'middle',1000)
    for m in range(15):
        x=left+m*unit
        c.el('line',x1=x,y1=106,x2=x,y2=top+5*row,stroke=LINE,stroke_width=1)
        c.text(x,98,str(m),24,GRAY,anchor='middle',width=65)
    stages=[('P0 本地原型',['任务、真实推理与版本闭环'],0,2),
            ('P1 领域验证',['独立标签、适配与同任务对照'],2,5),
            ('P2 银行离线评估',['任务映射、权限与旁路评价'],5,8),
            ('P3 有限辅助使用',['限定范围、监控与异常恢复'],8,11),
            ('P4 同类任务扩展',['新增任务逐项评价与验收'],11,14)]
    for i,(name,lines,start,end) in enumerate(stages):
        y=top+i*row
        c.rect(35,y-10,1430,row-5,'#F6FAFE' if i%2==0 else LIGHT,stroke='none',rx=0)
        c.plate(43,y+2,342,65)
        c.text(60,y+26,name,29,DEEP,True,width=307)
        c.text(60,y+59,lines[0],24,INK,width=307)
        for m in range(15):
            x=left+m*unit;c.el('line',x1=x,y1=y-10,x2=x,y2=y+row-15,stroke=LINE,stroke_width=1)
        x=left+start*unit;w=(end-start)*unit
        c.rect(x+3,y+12,w,42,'#C9DBEB',stroke='none',rx=3)
        c.rect(x,y+6,w,42,'url(#deep)' if i==0 else 'url(#blue)',stroke='none',rx=3)
        c.el('path',d=f'M{x+5},{y+9} H{x+w-5}',fill='none',stroke='#9EC9EC',stroke_width=2)
        c.text(x+w/2,y+35,f'M{start}—M{end}',24,'white',True,'middle',w-8)
        xe=left+end*unit
        c.el('polygon',points=f'{xe}, {y+1} {xe+10},{y+27} {xe},{y+53} {xe-10},{y+27}',fill=DEEP)
    c.text(50,603,'◆ 阶段验收节点',26,INK,width=400)
    c.text(1450,603,'时间窗口随启动安排细化',26,GRAY,anchor='end',width=660)
    c.note(654,'阶段转换依据表8-1的质量、权限和人员承接条件逐项验收。')
    figures.append(c.save())

    c=Canvas('mapping','工小审任务与核验事项包适配',520)
    c.box(40,25,440,325,'任务输入映射',['任务编号与核验类型','获准材料及有效版本','主体、期间与业务范围','原文片段及定位信息'])
    c.box(530,25,440,325,'核验组件处理',['规则检查输入条件','Jev回答限定问题','按需分析未决关系','记录来源、耗时与人员动作'])
    c.box(1020,25,440,325,'事项包输出映射',['建议、候选与模型来源','成对原文及检查范围','人员确认或纠正依据','未决事项与有效版本'])
    c.arrow(488,185,520,185);c.arrow(978,185,1010,185)
    c.band(395,'接口范围为辅助核验信息，审批授权与授信结果由原系统承接')
    c.note(498,'字段关系为适配设计，具体接口、岗位权限与部署环境由银行确认。')
    figures.append(c.save())

    c=Canvas('expansion','同类任务扩展与交付验收',365)
    titles=['明确新增任务','复用稳定组件','重新验证增量','按范围交付']
    lines=[['确定材料关系与答案','定义证据及责任人员'],['沿用版本与原文索引','配置任务和候选标准'],['新资料质量与关键错误','人员工时及完整成本'],['验收任务与使用范围','交付记录与异常恢复']]
    for i in range(4):
        x=40+i*365;c.box(x,25,325,185,titles[i],lines[i],size=27)
        if i<3:c.arrow(x+334,115,x+355,115)
    c.band(250,'先扩展相同材料关系的核验任务，再按证据确定下一步范围')
    c.note(349,'新任务分别验证，模型与业务范围按版本管理。')
    figures.append(c.save())

    (OUT/'manifest.json').write_text(json.dumps({'figures':figures,'scope':'16张新增正文图与4张替换图，沿用用户最新Word；协同配对图依据历史真实记录重算'},ensure_ascii=False,indent=2),encoding='utf-8')
    print('BLUE_VECTOR_ASSETS='+str(len(figures)))

if __name__ == '__main__':
    main()
