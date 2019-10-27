# -*- coding: utf-8 -*-
"""
功能：本程序从东方财富网提取流通股大股东最新情况，保存sqlite

"""
import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sqlite3
import sys
import os
import time
from pyquery import PyQuery as pq
from configobj import ConfigObj
import pandas as pd
import traceback
import re
import winreg
 
########################################################################
#初始化本程序配置文件
########################################################################
def iniconfig():
    inifile = os.path.splitext(sys.argv[0])[0]+'.ini'  #设置缺省配置文件
    return ConfigObj(inifile,encoding='GBK')


#########################################################################
#读取键值,如果键值不存在，就设置为defvl
#########################################################################
def readkey(config,key,defvl=None):
    keys = config.keys()
    if defvl==None :
        if keys.count(key) :
            return config[key]
        else :
            return ""
    else :
        if not keys.count(key) :
            config[key] = defvl
            config.write()
            return defvl
        else:
            return config[key]


###############################################################################
#万亿转换
###############################################################################
def wyzh(s):
    s=s.replace('万','*10000').replace('亿','*100000000')
    try:
        return eval(s)
    except:
        return None


###############################################################################
#字符串转数值
###############################################################################
def str2num(s):
    if '.' in s:
        try:
            return round(float(s),4)
        except:
            return None
    else:
        try:
            return int(s)
        except:
            return None

###############################################################################
#长股票代码
###############################################################################
def lgpdm(dm):
    return dm[:6]+('.SH' if dm[0]=='6' else '.SZ')

###############################################################################
#短股票代码
###############################################################################
def sgpdm(dm):
    return dm[:6]

###############################################################################
#从通达信系统读取股票代码表
###############################################################################
def get_gpdm():
    datacode = []
    for sc in ('h','z'):
        fn = gettdxdir()+'\\T0002\\hq_cache\\s'+sc+'m.tnf'
        f = open(fn,'rb')
        f.seek(50)
        ss = f.read(314)
        while len(ss)>0:
            gpdm=ss[0:6].decode('GBK')
            gpmc=ss[23:31].strip(b'\x00').decode('GBK').replace(' ','').replace('*','')
            gppy=ss[285:291].strip(b'\x00').decode('GBK')
            #剔除非A股代码
            if (sc=="h" and gpdm[0]=='6') :
                gpdm=gpdm+'.SH'
                datacode.append([gpdm,gpmc,gppy])
            if (sc=='z' and (gpdm[0:2]=='00' or gpdm[0:2]=='30')) :
                gpdm=gpdm+'.SZ'
                datacode.append([gpdm,gpmc,gppy])
            ss = f.read(314)
        f.close()
    gpdmb=pd.DataFrame(datacode,columns=['gpdm','gpmc','gppy'])
    gpdmb=gpdmb.set_index('gpdm')
    return gpdmb

########################################################################
#获取本机通达信安装目录，生成自定义板块保存目录
########################################################################
def gettdxdir():

    try :
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\华西证券华彩人生")
        value, type = winreg.QueryValueEx(key, "InstallLocation")
    except :
        print("本机未安装【华西证券华彩人生】软件系统。")
        sys.exit()
    return value

########################################################################
#获取本机通达信安装目录，生成自定义板块保存目录
########################################################################
def gettdxblkdir():
    try :
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\华西证券华彩人生")
        value, type = winreg.QueryValueEx(key, "InstallLocation")
        return value + '\\T0002\\blocknew'
    except :
        print("本机未安装【华西证券华彩人生】软件系统。")
        sys.exit()


#############################################################################
#股票列表,通达信板块文件调用时wjtype="tdxbk"
#############################################################################
def zxglist(zxgfn,wjtype=""):
    zxglst = []
    p = "(\d{6})"
    if wjtype == "tdxblk" :
        p ="\d(\d{6})"
    if os.path.exists(zxgfn) :
        #用二进制方式打开再转成字符串，可以避免直接打开转换出错
        with open(zxgfn,'rb') as dtf:
            zxg = dtf.read()
            if zxg[:3] == b'\xef\xbb\xbf' :
                zxg = zxg.decode('UTF8','ignore')   #UTF-8
            elif zxg[:2] == b'\xfe\xff' :
                zxg = zxg.decode('UTF-16','ignore')  #Unicode big endian
            elif zxg[:2] == b'\xff\xfe' :
                zxg = zxg.decode('UTF-16','ignore')  #Unicode
            else :
                zxg = zxg.decode('GBK','ignore')      #ansi编码
        zxglst =re.findall(p,zxg)
    else:
        print("文件%s不存在！" % zxgfn)
    if len(zxglst)==0:
        print("股票列表为空,请检查%s文件。" % zxgfn)

    zxg = list(set(zxglst))
    zxg.sort(key=zxglst.index)

    return zxg

#############################################################################
#通达信自选股A股列表，去掉了指数代码
#############################################################################    
def zxglst():
    zxgfile="zxg.blk"
    tdxblkdir = gettdxblkdir()
    zxgfile = os.path.join(tdxblkdir,zxgfile)
    zxg = zxglist(zxgfile,"tdxblk")
    
    gpdmb=get_gpdm()
    
    #去掉指数代码只保留A股代码
    zxglb=[]
    for e in zxg:
        dm=lgpdm(e)
        if dm in gpdmb.index:
            zxglb.append(dm)
            
    return zxglb

##########################################################################
#获取运行程序所在驱动器
##########################################################################
def getdrive():
    if sys.argv[0]=='' :
        return os.path.splitdrive(os.getcwd())[0]
    else:
        return os.path.splitdrive(sys.argv[0])[0]


##########################################################################
#股票基本信息
##########################################################################
def get_ssrq():
    csvfn = r'D:\selestock\all.csv'
    df = pd.read_csv(csvfn, dtype={'code':'object'})
    df = df.set_index('code')
    df['gpdm'] = df.index.map(lambda x:x+('.SH' if x[0]=='6' else '.SZ'))
    df['ssrq'] = df['timeToMarket'].map(lambda x:str(x) if x>0 else '')
    df = df.set_index('gpdm')
    return df[['ssrq']]


###############################################################################
#读取过研报的股票代码表
###############################################################################
def del_gpdm(rq=None):

    dbfn=getdrive()+'\\hyb\\STOCKDATA.db'
    dbcn = sqlite3.connect(dbfn)
    curs = dbcn.cursor()
    if rq==None:
        sql='select gpdm from (select gpdm,count(*) as ts from ltg group by gpdm) where ts>2;'        
    else:
        sql='select distinct gpdm from ltg where rq>="%s";' % rq

    curs.execute(sql)        
    data = curs.fetchall()

    cols = ['gpdm']
    
    df=pd.DataFrame(data,columns=cols)
    df=df.set_index('gpdm')
    
    return df

###############################################################################
#十大流通股东数据
###############################################################################
def dl_ltg_gpdm():
    dmb=[]
    #报告其实年份
    ssrq=get_ssrq()
    ssrq['qsnf']=ssrq['ssrq'].map(lambda x:x[:4] if x!=None else None)        
    ssrq['qsnf']=ssrq['qsnf'].map(lambda x:'2012' if x!='' and x<'2012' else x)        
    
    dbfn=getdrive()+'\\hyb\\STOCKDATA.db'
    dbcn = sqlite3.connect(dbfn)
    curs = dbcn.cursor()

    sql='select gpdm,substr(rq,1,4) as nf,count(*) as bgs from ltg  group by gpdm,nf order by gpdm,nf;'

    curs.execute(sql)        
    data = curs.fetchall()
    
    dbcn.close()            

    cols=['gpdm','nf','bgs']
    df=pd.DataFrame(data,columns=cols)
    df=df.set_index('gpdm')

    for dm, row in ssrq.iterrows():
        ss,qs=row
        if dm in df.index:
            gpdf=df.loc[dm]
    
            nfbgs={}
            if isinstance(gpdf,pd.DataFrame):        
                for i,r in gpdf.iterrows():
                    nf,bgs=r
                    nfbgs[nf]=bgs
            elif isinstance(gpdf,pd.Series):
                nf,bgs=gpdf
                nfbgs[nf]=bgs
                
            #除开始年份和当年外，报告是不能少于4
                        
            if ss<'2012-03-01' and ('2012' not in nfbgs.keys() or nfbgs['2012']<4) and dm not in dmb:
                dmb.append(dm)

            if ss[4:]<'-03-01' and (qs not in nfbgs.keys() or nfbgs[qs]<4) and dm not in dmb:
                dmb.append(dm)
                
            if ss[4:]<'-06-01' and (qs not in nfbgs.keys() or nfbgs[qs]<3) and dm not in dmb:
                dmb.append(dm)

            if ss[4:]<'-09-01' and (qs not in nfbgs.keys() or nfbgs[qs]<2) and dm not in dmb:
                dmb.append(dm)

            if ss[4:]<'-12-01' and (qs not in nfbgs.keys() or nfbgs[qs]<1) and dm not in dmb:
                dmb.append(dm)

            y=datetime.datetime.today().year

            for nf in range(int(qs)+1,y):
                if (str(nf) not in nfbgs.keys() or nfbgs[str(nf)]<4) and dm not in dmb:
                    dmb.append(dm)
                    
            if str(y) in nfbgs.keys() and nfbgs[str(y)]<2 and dm not in dmb:
                dmb.append(dm)
    
        else:
            
            dmb.append(dm)
    
    
    return dmb
###############################################################################
#读取过研报的股票代码表
###############################################################################
def dlltg_gpdms():
    dbfn=getdrive()+'\\hyb\\STOCKDATA.db'
    dbcn = sqlite3.connect(dbfn)
    curs = dbcn.cursor()

    sql='select gpdm,substr(rq,1,4) as nf,count(*) from ltg group by gpdm,nf order by gpdm,nf'

    curs.execute(sql)        
    data = curs.fetchall()
    cols = ['gpdm','nf','bgs']
    
    df=pd.DataFrame(data,columns=cols)

    data=[]
    dm=''
    nf=''
    for i, row in df.iterrows():
        gpdm,nf,bgs=row
        if dm!=gpdm:        #新的一个股票
            dm=gpdm
        else:
            #
            if ((nf!='2018' and bgs<4) or (nf=='2018' and bgs==1)) and dm not in data:
                data.append(dm)

    dbcn.close()            
    return data

###############################################################################
#读取过研报的股票代码表
###############################################################################
def del_gpdm2():
    
    ssrq=get_ssrq()
    y1=datetime.datetime.now().year
    
    ssrq['bgqs']=ssrq['ssrq'].map(lambda x: None if x=='' else int(x[:4])).map(lambda x:2012 if x<2012 else x).map(lambda x:(y1-x)*4+2)
    
    dbfn=getdrive()+'\\hyb\\STOCKDATA.db'
    dbcn = sqlite3.connect(dbfn)
    curs = dbcn.cursor()
    sql='select gpdm,count(*) as bgs from ltg group by gpdm;'        

    curs.execute(sql)        
    data = curs.fetchall()

    cols = ['gpdm','bgs']
    
    df=pd.DataFrame(data,columns=cols)
    df=df.set_index('gpdm')
    
    df=df.join(ssrq)
    
    return df

###############################################################################
#预约披露日期
###############################################################################
def get_yyrq():
    dbfn=getdrive()+'\\hyb\\STOCKEPS.db'
    dbcn = sqlite3.connect(dbfn)
    curs = dbcn.cursor()
    
    sql = 'select gpdm,yyrq from yysj;'
    
    curs.execute(sql)
    
    data = curs.fetchall()
    cols = ['gpdm','yyrq']
    
    df = pd.DataFrame(data,columns=cols)
    df = df.set_index('gpdm')

    dbcn.close()    

    return df



###############################################################################
#十大流通股东数据
###############################################################################
def get_data(dm,html,rq):
    html = pq(html)
    html.find("script").remove()    # 清理 <script>...</script>
    html.find("style").remove()     # 清理 <style>...</style>
    rows=html('tr')
    sl=0
    bl=0
    gs=0    
    for i in range(1,len(rows)):
        row=pq(rows.eq(i))
        cgsl=row('td').eq(3).text().replace(',','')
        cgbl=row('td').eq(4).text()
        if str2num(cgsl)!=None and str2num(cgbl)!=None :
            sl=sl+str2num(cgsl)
            bl=bl+str2num(cgbl)
            gs=gs+1
    
    if bl>0 and gs>0 :
        ltg=sl/bl*100
        sh=ltg-sl
        ltg=round(ltg/100000000,2)
        sl=round(sl/100000000,2)
        bl=round(bl,2)    
        sh=round(sh,0)
        return [lgpdm(dm),rq,ltg,sl,bl,sh,gs]
    else:
        return None
        
###############################################################################
#十大流通股东数据
###############################################################################
def readsdltgd(browser,dm,dbcn):

    data=[]

    url='http://data.eastmoney.com/gdfx/stock/%s.html' % sgpdm(dm)

#    browser = webdriver.Firefox()
    browser.get(url)

    elem=WebDriverWait(browser, 30).until(
        EC.presence_of_element_located((By.XPATH,'//dl[@id=\"datelistLt\"]')))

    dds=elem.find_elements_by_tag_name('dd')
    if len(dds)<6:
        for i in range(len(dds)):
            try:
                dds[i].click()
                rq=dds[i].text
                time.sleep(0.1)
                tbl=browser.find_element_by_xpath('//table[@id=\"tb_ltgd\"]')
                html=tbl.get_attribute('innerHTML')
                dt=get_data(dm,html,rq)
                if dt!=None:
                    data.append(dt)
                else:
                    print('Err:%s,%s'%(dm,rq))                    
                    #第一次公告可能没有比例，非第一次公告则表明读取失败
#                    if i<len(dds)-1:
#                        return False
                    
            except:
                return False
                
            
    if len(dds)==6:        
        elem1=elem.find_element_by_xpath('//div[@class=\"dropdownList\"]/ul')
        
        browser.execute_script('arguments[0].setAttribute("class","");', elem1)
        
        lis=elem1.find_elements_by_tag_name('li')
        for i in range(1,len(lis)):     
            try:
#                browser.execute_script('arguments[0].setAttribute("class","");', elem1)
#                browser.execute_script('arguments[0].setAttribute("class","over");', lis[i])
                browser.execute_script('arguments[0].click();', lis[i])
#                browser.execute_script('arguments[0].setAttribute("class","");', lis[i])
#                browser.execute_script('arguments[0].setAttribute("class","hide");', elem1)
    
                time.sleep(0.2)
                rq=browser.find_element_by_xpath('//div[@class=\"dropdownList\"]/span').text
    
                tbl=browser.find_element_by_xpath('//table[@id=\"tb_ltgd\"]')
                html=tbl.get_attribute('innerHTML')
#                print(rq,html)
                dt=get_data(dm,html,rq)
                if dt!=None:
                    data.append(dt)
                else:
                    print('READ Err:%s,%s'%(dm,rq))
                    #第一次公告可能没有比例，非第一次公告则表明读取失败
#                    if i<len(lis)-1:
#                        return False
            except:
                return False
                
    if len(data)>0:
#        print(data)
        try:
            dbcn.executemany('''INSERT OR REPLACE INTO LTG (GPDM,RQ,LTG,SDGDCG,SDGDZB,SHCG,DGDGS)
            VALUES (?,?,?,?,?,?,?)''', data)
            dbcn.commit()
        except:
            print('SAVE ERR')
            return False
        
    return True   
   
if __name__ == "__main__": 
#def tmp():
#    sys.exit()
    
    print('%s Running' % sys.argv[0])

    gpdmb=get_gpdm()
 
    #去掉已提取的
#    delgpdm=del_gpdm('2018-06-30')    
#    delgpdm=del_gpdm()    
#    gpdmb=gpdmb[~gpdmb.index.isin(delgpdm.index)]  

    dlltggpdm=dl_ltg_gpdm()    
    gpdmb=gpdmb[gpdmb.index.isin(dlltggpdm)]  


#    td = datetime.datetime.now().strftime('%Y-%m-%d')
#    td1=(datetime.datetime.now()+datetime.timedelta(-60)).strftime("%Y-%m-%d")
#    yyrq=get_yyrq()
#    yyrq=yyrq[yyrq['yyrq']>=td1]
#    yyrq=yyrq[yyrq['yyrq']<=td]
#
#    gpdmb=gpdmb[gpdmb.index.isin(yyrq.index)]

#    gpdmb=gpdmb[gpdmb.index.isin(['600074.SH'])]

    #自选股
#    zxg=zxglst()
#    gpdmb=gpdmb[gpdmb.index.isin(zxg)]

    dbfn=getdrive()+'\\hyb\\STOCKDATA.db'
    dbcn = sqlite3.connect(dbfn)

    fireFoxOptions = webdriver.FirefoxOptions()
    fireFoxOptions.set_headless()
    browser = webdriver.Firefox(firefox_options=fireFoxOptions)

#    browser = webdriver.Firefox()

    now1 = datetime.datetime.now().strftime('%H:%M:%S')
    print('开始读取时间：%s' % now1)
    j=0
    for i in range(j,len(gpdmb)):
        gpdm=gpdmb.index[i]
        gpmc = gpdmb.iloc[i]['gpmc']
        print("共有%d只股票，正在处理第%d只：%s%s，请等待…………" % (len(gpdmb),i+1,gpdm,gpmc)) 

        if readsdltgd(browser,gpdm,dbcn):
            print('%s%s读取成功||'%(gpdm,gpmc))
        else:
            print('%s%s读取失败--'%(gpdm,gpmc))

        if i!=0 and (i % 10 == 0) and i!=len(gpdmb)-1:     #   重启浏览器可以避免系统崩溃，很重要！！！
            browser.quit()
            time.sleep(10)
            fireFoxOptions = webdriver.FirefoxOptions()
            fireFoxOptions.set_headless()
            browser = webdriver.Firefox(firefox_options=fireFoxOptions)

#            browser = webdriver.Firefox()
            

    dbcn.close()

    browser.quit()        

    now2 = datetime.datetime.now().strftime('%H:%M:%S')
    print('开始运行时间：%s' % now1)
    print('结束运行时间：%s' % now2)

