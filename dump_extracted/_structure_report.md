```

==========================================================================================
[1] 인코딩 확인 - 선언부 vs 실제 바이트
==========================================================================================
- 트래블월렛: 선언=utf-8 / 실제 UTF-8 디코드=성공 / 실제 CP949 디코드=FAIL: 'cp949' codec can't decode byte 0xec in position 193: illegal multibyte sequence
- 핀샷: 선언=utf-8 / 실제 UTF-8 디코드=성공 / 실제 CP949 디코드=FAIL: 'cp949' codec can't decode byte 0xec in position 193: illegal multibyte sequence
- 아이씨비: 선언=utf-8 / 실제 UTF-8 디코드=성공 / 실제 CP949 디코드=FAIL: 'cp949' codec can't decode byte 0xec in position 193: illegal multibyte sequence
- 이롬넷: 선언=utf-8 / 실제 UTF-8 디코드=성공 / 실제 CP949 디코드=FAIL: 'cp949' codec can't decode byte 0xec in position 193: illegal multibyte sequence
- 센트비: 선언=utf-8 / 실제 UTF-8 디코드=성공 / 실제 CP949 디코드=FAIL: 'cp949' codec can't decode byte 0xec in position 193: illegal multibyte sequence

==========================================================================================
[2] 최상위 구조 (depth 1~2)
==========================================================================================

--- 트래블월렛 ---
  DOCUMENT  (x1)
    DOCUMENT-NAME  (x1)
    FORMULA-VERSION  (x1)
    COMPANY-NAME  (x1)
    SUMMARY  (x1)
    BODY  (x1)

--- 핀샷 ---
  DOCUMENT  (x1)
    DOCUMENT-NAME  (x1)
    FORMULA-VERSION  (x1)
    COMPANY-NAME  (x1)
    SUMMARY  (x1)
    BODY  (x1)

--- 아이씨비 ---
  DOCUMENT  (x1)
    DOCUMENT-NAME  (x1)
    FORMULA-VERSION  (x1)
    COMPANY-NAME  (x1)
    SUMMARY  (x1)
    BODY  (x1)

--- 이롬넷 ---
  DOCUMENT  (x1)
    DOCUMENT-NAME  (x1)
    FORMULA-VERSION  (x1)
    COMPANY-NAME  (x1)
    SUMMARY  (x1)
    BODY  (x1)

--- 센트비 ---
  DOCUMENT  (x1)
    DOCUMENT-NAME  (x1)
    FORMULA-VERSION  (x1)
    COMPANY-NAME  (x1)
    SUMMARY  (x1)
    BODY  (x1)

==========================================================================================
[2-비교] 5개 파일 depth1 태그 공통점/차이
==========================================================================================
공통 depth1 태그: ['DOCUMENT']

==========================================================================================
[3] 섹션 식별 (원문 300자 발췌)
==========================================================================================

--- 트래블월렛 ---
  감사의견: 위치=7079바이트, 의견종류키워드=판정불가
    발췌: 감사의견</SPAN>우리는 주식회사 트래블월렛(이하 "회사")의 재무제표를 감사하였습니다. 해당 재무제표는 2025년 12월 31일 및 2024년 12월 31일 현재의 재무상태표, 동일로 종료되는 양 보고기간의 손익계산서, 자본변동표, 현금흐름표 그리고 유의적인 회계정책의 요약을 포함한 재무제표의 주석으로 구성되어 있습니다.우리의 의견으로는 별첨된 회사의 재무제표는 회사의 2025년 12월 31일 및 2024년 12월 31일 현재의 재무상태와 동일로 종료되는 양 보고기간의 재무성과 및 현금흐름을 일반기업회계기준에 따라, 중요성의 관
  굵은 소제목 전체: ['감사의견근거', '재무제표에 대한 경영진과 지배기구의 책임 ', '재무제표감사에 대한 감사인의 책임']
  계속기업_관련_불확실성: 없음 (표준 4개 소제목만 존재, '계속기업'단어는 보일러플레이트 문장에만 등장)
  재무상태표: 위치=14649바이트, TITLE텍스트="재 무 상 태 표"
    발췌: >재 무 상 태 표</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="753" BORDER="0">  <COLGROUP WIDTH="753"> <COL WIDTH="300"></COL> <COL WIDTH="453"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="744" HEIGHT="23">제 9 기 2025년
  손익계산서: 위치=42180바이트, TITLE텍스트="손 익 계 산 서"
    발췌: >손 익 계 산 서</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="667" BORDER="0">  <COLGROUP WIDTH="667"> <COL WIDTH="300"></COL> <COL WIDTH="367"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="658" HEIGHT="23">제 9 기 2025년
  현금흐름표: 위치=71590바이트, TITLE텍스트="현 금 흐 름 표"
    발췌: >현 금 흐 름 표</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="824" BORDER="0">  <COLGROUP WIDTH="824"> <COL WIDTH="300"></COL> <COL WIDTH="524"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="815" HEIGHT="23">제 9 기 2025년
  주석_시작지점: 위치=98871바이트
    발췌: >주석</TITLE>  <TABLE ACLASS="NORMAL" AFIXTABLE="N" WIDTH="600" BORDER="0">  <COLGROUP WIDTH="600"> <COL WIDTH="600"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD ALIGN="CENTER" WIDTH="591" HEIGHT="23">제 9 기 2025년 12월 31일 현재</TD> </TR>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> 

--- 핀샷 ---
  감사의견: 위치=8201바이트, 의견종류키워드=판정불가
    발췌: 감사의견</P> <P USERMARK="F-11 ">우리는 주식회사 핀샷(이하 '회사')의 재무제표를 감사하였습니다. 동 재무제표는 2025년 12월 31일과 2024년 12월 31일 현재의 재무상태표, 동일로 종료되는 양 보고기간의 손익계산서, 자본변동표 및 현금흐름표 그리고 유의적 회계정책에 대한 요약을 포함한 재무제표의 주석으로 구성되어있습니다.</P> <P USERMARK="F-11 "> 우리의 의견으로는 별첨된 회사의 재무제표는 회사의 2025년 12월 31일과 2024년 12월 31일 현재의 재무상태와 동일로 종료되는 양
  굵은 소제목 전체: []
  계속기업_관련_불확실성: 없음 (표준 4개 소제목만 존재, '계속기업'단어는 보일러플레이트 문장에만 등장)
  재무상태표: 위치=15550바이트, TITLE텍스트="재 무 상 태 표"
    발췌: >재 무 상 태 표</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="630" BORDER="0">  <COLGROUP WIDTH="630"> <COL WIDTH="300"></COL> <COL WIDTH="330"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="621" USERMARK="F-BT " HEIGHT
  손익계산서: 위치=49367바이트, TITLE텍스트="손 익 계 산 서"
    발췌: >손 익 계 산 서</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="630" BORDER="0">  <COLGROUP WIDTH="630"> <COL WIDTH="300"></COL> <COL WIDTH="330"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="621" USERMARK="F-BT " HEIGHT
  현금흐름표: 위치=86770바이트, TITLE텍스트="현 금 흐 름 표"
    발췌: >현 금 흐 름 표</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="629" BORDER="0">  <COLGROUP WIDTH="629"> <COL WIDTH="301"></COL> <COL WIDTH="328"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="620" USERMARK="F-BT " HEIGHT
  주석_시작지점: 위치=118161바이트
    발췌: >주석</TITLE>  <TABLE ACLASS="NORMAL" AFIXTABLE="N" WIDTH="601" BORDER="0">  <COLGROUP WIDTH="601"> <COL WIDTH="601"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD WIDTH="592" USERMARK="F-BT " VALIGN="MIDDLE" ALIGN="CENTER" HEIGHT="23">제 10(당) 기 2025년 1월 1일부터 2025년 12월 31일까지</

--- 아이씨비 ---
  감사의견: 위치=8847바이트, 의견종류키워드=판정불가
    발췌: 감사의견</P> <P>우리는 주식회사 아이씨비(이하 "회사")의 재무제표를 감사하였습니다. 해당 재무제표는 2025년 12월 31일과 2024년 12월 31일 현재의 재무상태표, 동일로 종료되는 양 보고기간의 손익계산서, 자본변동표 및 현금흐름표 그리고 유의적 회계정책에의 요약을 포함한 재무제표의 주석으로 구성되어 있습니다.우리의 의견으로는 별첨된 회사의 재무제표는 회사의 2025년 12월 31일과 2024년 12월 31일 현재의 재무상태와 동일로 종료되는 양 보고기간의 재무성과 및 현금흐름을 일반기업회계기준에 따라, 중요성의 관점
  굵은 소제목 전체: ['감사의견', '감사의견근거', '재무제표에 대한 경영진과 지배기구의 책임', '재무제표감사에 대한 감사인의 책임']
  계속기업_관련_불확실성: 없음 (표준 4개 소제목만 존재, '계속기업'단어는 보일러플레이트 문장에만 등장)
  재무상태표: 위치=15840바이트, TITLE텍스트="재 무 상 태 표"
    발췌: >재 무 상 태 표</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="818" BORDER="0">  <COLGROUP WIDTH="818"> <COL WIDTH="300"></COL> <COL WIDTH="518"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="809" HEIGHT="23">제 13(당) 기 2
  손익계산서: 위치=50946바이트, TITLE텍스트="손 익 계 산 서"
    발췌: >손 익 계 산 서</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="823" BORDER="0">  <COLGROUP WIDTH="823"> <COL WIDTH="300"></COL> <COL WIDTH="523"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="814" HEIGHT="23">제 13(당) 기 2
  현금흐름표: 위치=89207바이트, TITLE텍스트="현 금 흐 름 표"
    발췌: >현 금 흐 름 표</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="826" BORDER="0">  <COLGROUP WIDTH="826"> <COL WIDTH="300"></COL> <COL WIDTH="526"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="817" HEIGHT="23">제 13(당) 기 2
  주석_시작지점: 위치=121448바이트
    발췌: >주석</TITLE>  <TABLE ACLASS="NORMAL" AFIXTABLE="N" WIDTH="600" BORDER="0">  <COLGROUP WIDTH="600"> <COL WIDTH="600"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD WIDTH="591" HEIGHT="23" VALIGN="MIDDLE" ALIGN="CENTER">제 13(당) 기 2025년 12월 31일 현재</TD> </TR>  <TR ACOPY="Y" ADELE

--- 이롬넷 ---
  감사의견: 위치=4593바이트, 의견종류키워드=판정불가
    발췌: 감사의견</P> <P>우리는 주식회사 이롬넷(이하 "회사")의 재무제표를 감사하였습니다. 해당 재무제표는 2025년 12월 31일과 2024년 12월 31일 현재의 재무상태표, 동일로 종료되는 양 보고기간의 손익계산서, 자본변동표, 현금흐름표 그리고 유의적인 회계정책의 요약을 포함한 재무제표의 주석으로 구성되어 있습니다.</P> <P> </P> <P>우리의 의견으로는 별첨된 회사의 재무제표는 회사의 2025년 12월 31일과 2024년 12월 31일 현재의 재무상태와 동일로 종료되는 양 보고기간의 재무성과 및 현금흐름을 대한민국의 
  굵은 소제목 전체: ['감사의견', '감사의견근거', '재무제표에 대한 경영진과 지배기구의 책임', '재무제표감사에 대한 감사인의 책임']
  계속기업_관련_불확실성: 없음 (표준 4개 소제목만 존재, '계속기업'단어는 보일러플레이트 문장에만 등장)
  재무상태표: 위치=11657바이트, TITLE텍스트="재 무 상 태 표"
    발췌: >재 무 상 태 표</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="776" BORDER="0">  <COLGROUP WIDTH="776"> <COL WIDTH="300"></COL> <COL WIDTH="476"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="767" HEIGHT="23">제 10 기 2025
  손익계산서: 위치=41105바이트, TITLE텍스트="손 익 계 산 서"
    발췌: >손 익 계 산 서</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="777" BORDER="0">  <COLGROUP WIDTH="777"> <COL WIDTH="300"></COL> <COL WIDTH="477"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="768" HEIGHT="23">제10기 2025년 
  현금흐름표: 위치=72459바이트, TITLE텍스트="현 금 흐 름 표"
    발췌: >현 금 흐 름 표</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="792" BORDER="0">  <COLGROUP WIDTH="792"> <COL WIDTH="300"></COL> <COL WIDTH="492"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="783" HEIGHT="23">제 10 기 2025
  주석_시작지점: 위치=100923바이트
    발췌: >주석</TITLE>  <TABLE ACLASS="NORMAL" AFIXTABLE="N" WIDTH="600" BORDER="0">  <COLGROUP WIDTH="600"> <COL WIDTH="600"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD ALIGN="CENTER" WIDTH="591" HEIGHT="23">제 10기 2025년 01월 01일부터 2025년 12월 31일까지</TD> </TR>  <TR ACOPY="Y" ADELETE="Y

--- 센트비 ---
  감사의견: 위치=7711바이트, 의견종류키워드=판정불가
    발췌: 감사의견</P> <P>우리는 주식회사 센트비(이하 “회사”)의 재무제표를 감사하였습니다. 해당 재무제표는 2025년 12월 31일과 2024년 12월 31일 현재의 재무상태표 및 동일로 종료되는양 보고기간의 손익계산서, 자본변동표, 현금흐름표 그리고 유의적인 회계정책의 요약을 포함한 재무제표의 주석으로 구성되어 있습니다.</P> <P></P> <P>우리의 의견으로는 별첨된 회사의 재무제표는 회사의 2025년 12월 31일과 2024년 12월 31일 현재의 재무상태와 동일로 종료되는 양 보고기간의 재무성과 및 현금흐름을 일반기업회계기
  굵은 소제목 전체: ['감사의견', '감사의견근거', '재무제표에 대한 경영진과 지배기구의 책임', '재무제표감사에 대한 감사인의 책임']
  계속기업_관련_불확실성: 없음 (표준 4개 소제목만 존재, '계속기업'단어는 보일러플레이트 문장에만 등장)
  재무상태표: 위치=14413바이트, TITLE텍스트="재 무 상 태 표"
    발췌: >재 무 상 태 표</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="600" BORDER="0">  <COLGROUP WIDTH="600"> <COL WIDTH="300"></COL> <COL WIDTH="300"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="591" HEIGHT="23">제 11 기 2025
  손익계산서: 위치=44919바이트, TITLE텍스트="손 익 계 산 서"
    발췌: >손 익 계 산 서</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="600" BORDER="0">  <COLGROUP WIDTH="600"> <COL WIDTH="300"></COL> <COL WIDTH="300"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="591" HEIGHT="23">제 11(당) 기  
  현금흐름표: 위치=74319바이트, TITLE텍스트="현 금 흐 름 표"
    발췌: >현 금 흐 름 표</TITLE>  <TABLE ACLASS="EXTRACTION" AFIXTABLE="Y" WIDTH="600" BORDER="0">  <COLGROUP WIDTH="600"> <COL WIDTH="300"></COL> <COL WIDTH="300"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD COLSPAN="2" ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="591" HEIGHT="23">제 11(당) 기  
  주석_시작지점: 위치=98640바이트
    발췌: >주석</TITLE>  <TABLE ACLASS="NORMAL" AFIXTABLE="N" WIDTH="600" BORDER="0">  <COLGROUP WIDTH="600"> <COL WIDTH="600"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD ALIGN="CENTER" WIDTH="591" HEIGHT="23">제 11(당) 기  2025년 12월 31일 현재</TD> </TR>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="

==========================================================================================
[4] 주석 항목 존재여부 (정확한 원문 제목)
==========================================================================================
항목                    트래블월렛         핀샷            아이씨비          이롬넷           센트비           
특수관계자거래               없음            없음            있음            있음            있음            
소송_우발부채_충당부채          있음            있음            있음            있음            있음            
CB_BW_RCPS            없음            없음            없음            없음            있음            
주주구성_지분율              있음            있음            있음            있음            있음            
매출처_거래처집중도            없음            없음            없음            없음            없음            

[상세 발췌 - 있음으로 판정된 것들의 원문 주변]

--- 트래블월렛 ---
  특수관계자거래: 없음
  소송_우발부채_충당부채: ...,607 8,780      14. 우발 채무와 주요약정사항  (1) 당기말과 전...
  CB_BW_RCPS: 없음
  주주구성_지분율: ... 납입 자본금은 9,329백만원이며 주주현황은 다음과 같습니다.         ...
  매출처_거래처집중도: 없음

--- 핀샷 ---
  특수관계자거래: 없음
  소송_우발부채_충당부채: ...수 없습니다.  2.10 충당부채와 우발부채 당사는 과거사건이나 거래의 결과로 ...
  CB_BW_RCPS: 없음
  주주구성_지분율: ...현이며, 대표이사와 그 특수관계인의 지분율은  100%입니다. 2. 중요한 회...
  매출처_거래처집중도: 없음

--- 아이씨비 ---
  특수관계자거래: ... 하지 않았습니다.      22. 특수관계자거래  (1) 보고기간종료일 현재 당사의...
  소송_우발부채_충당부채: ...고 있습니다.  (12) 충당부채와 우발부채 당사는 과거사건이나 거래의 결과로 ...
  CB_BW_RCPS: 없음
  주주구성_지분율: ...,585천원입니다.당기말 현재 주요 주주현황은 다음과 같습니다.         ...
  매출처_거래처집중도: 없음

--- 이롬넷 ---
  특수관계자거래: ...,613 218,048    11. 특수관계자 공시 (1) 특수관계자 등의 현황    ...
  소송_우발부채_충당부채: ...성위험을 관리하고 있습니다. 19. 우발부채와 주요 약정사항당기말 현재 당사의 ...
  CB_BW_RCPS: 없음
  주주구성_지분율: ...천원이며, 보고기간종료일 현재 주요 주주현황은 다음과 같습니다.         ...
  매출처_거래처집중도: 없음

--- 센트비 ---
  특수관계자거래: ...급여로 반영하고 있습니다.  11. 특수관계자 거래 (1) 보고기간종료일 당사의 특수관...
  소송_우발부채_충당부채: ...16,687,392      17. 우발채무와 약정사항(1) 보고기간종료일 현재...
  CB_BW_RCPS: ... 우선주3       우선주의 종류 상환전환우선주식(누적적, 참가적) 상환전환우선주식...
  주주구성_지분율: ...6,000,489,000원으로 주요 주주현황은 다음과 같습니다.         ...
  매출처_거래처집중도: 없음

==========================================================================================
[5] 표 마크업 스키마 (TD 계열 vs TE ACODE 계열)
==========================================================================================

--- 트래블월렛 ---
  <TE 태그 수: 877  |  <TD 태그 수: 1083
  TABLE ACLASS=FINANCE: 4건  |  ACLASS=NORMAL: 75건  |  ACLASS=EXTRACTION: 11건
  TE 태그 원문 예시: <TE ACODE="11000000000000" ADELIM="0" ALEVEL="0" WIDTH="218" HEIGHT="23">자산
  TD 태그 원문 예시: <TD CLASS="NORMAL" VALIGN="MIDDLE" WIDTH="591" COLSPAN="2" USERMARK="F-BT14 " ALIGN="CENTER" HEIGHT="27">제 9 기

--- 핀샷 ---
  <TE 태그 수: 908  |  <TD 태그 수: 736
  TABLE ACLASS=FINANCE: 4건  |  ACLASS=NORMAL: 71건  |  ACLASS=EXTRACTION: 11건
  TE 태그 원문 예시: <TE ACODE="11000000000000" ADELIM="0" ALEVEL="0" USERMARK="F-BT " WIDTH="263" HEIGHT="23">자                           산
  TD 태그 원문 예시: <TD CLASS="NORMAL" VALIGN="MIDDLE" WIDTH="591" COLSPAN="2" ALIGN="CENTER" USERMARK="F-BT12 " HEIGHT="27">제 10 기

--- 아이씨비 ---
  <TE 태그 수: 1073  |  <TD 태그 수: 1296
  TABLE ACLASS=FINANCE: 4건  |  ACLASS=NORMAL: 111건  |  ACLASS=EXTRACTION: 11건
  TE 태그 원문 예시: <TE ACODE="11000000000000" ADELIM="0" ALEVEL="0" WIDTH="277" HEIGHT="23">자산
  TD 태그 원문 예시: <TD ALIGN="CENTER" VALIGN="MIDDLE" WIDTH="591" HEIGHT="32" USERMARK="F-BT18 ">주식회사 아이씨비

--- 이롬넷 ---
  <TE 태그 수: 922  |  <TD 태그 수: 1098
  TABLE ACLASS=FINANCE: 4건  |  ACLASS=NORMAL: 85건  |  ACLASS=EXTRACTION: 11건
  TE 태그 원문 예시: <TE ACODE="11000000000000" ADELIM="0" ALEVEL="0" WIDTH="265" HEIGHT="23">자                     산
  TD 태그 원문 예시: <TD CLASS="NORMAL" VALIGN="MIDDLE" WIDTH="591" COLSPAN="2" ALIGN="CENTER" USERMARK="F-BT14 " HEIGHT="27">제 10 기

--- 센트비 ---
  <TE 태그 수: 862  |  <TD 태그 수: 841
  TABLE ACLASS=FINANCE: 4건  |  ACLASS=NORMAL: 49건  |  ACLASS=EXTRACTION: 11건
  TE 태그 원문 예시: <TE ACODE="11000000000000" ADELIM="0" ALEVEL="0" WIDTH="214" HEIGHT="23">자                        산
  TD 태그 원문 예시: <TD CLASS="NORMAL" VALIGN="MIDDLE" WIDTH="591" HEIGHT="27" COLSPAN="2" ALIGN="CENTER" USERMARK="F-BT14 ">제 11 기

==========================================================================================
[6] 목차(TOC) 존재여부
==========================================================================================

--- 트래블월렛 ---
  목차: 위치=3538바이트
    발췌: 목              차</TITLE> <P></P> <P></P> <P></P>  <TABLE ACLASS="NORMAL" AFIXTABLE="N" BORDER="0" WIDTH="602">  <COLGROUP WIDTH="602"> <COL WIDTH="302"></COL> <COL WIDTH="300"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD WIDTH="293" HEIGHT="23" VALIGN="MIDDLE">I. 독립된 감사인의 
  ATOC="Y" (목차와 연결되는 섹션 표시) 태그 목록: [('2', '독립된 감사인의 감사보고서'), ('3', '(첨부)재 무 제 표'), ('4', '재 무 상 태 표'), ('5', '손 익 계 산 서'), ('6', '자 본 변 동 표'), ('7', '현 금 흐 름 표'), ('8', '주석'), ('9', '외부감사 실시내용')]

--- 핀샷 ---
  목차: 위치=3525바이트
    발췌: 목              차</TITLE> <P></P> <P></P>  <TABLE AFIXTABLE="N" BORDER="0" WIDTH="600" ACLASS="NORMAL">  <COLGROUP WIDTH="600"> <COL WIDTH="25"></COL> <COL WIDTH="550"></COL> <COL WIDTH="25"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="31"> <TD USERMARK="F-BT " WIDTH="566" COLSPAN="
  ATOC="Y" (목차와 연결되는 섹션 표시) 태그 목록: [('2', '독립된 감사인의 감사보고서'), ('3', '(첨부)재 무 제 표'), ('4', '재 무 상 태 표'), ('5', '손 익 계 산 서'), ('11', '자 본 변 동 표'), ('7', '현 금 흐 름 표'), ('8', '주석'), ('9', '외부감사 실시내용')]

--- 아이씨비 ---
  목차: 위치=3975바이트
    발췌: 목              차</TITLE> <P></P>  <TABLE ACLASS="NORMAL" AFIXTABLE="N" BORDER="0" WIDTH="609">  <COLGROUP WIDTH="609"> <COL WIDTH="223"></COL> <COL WIDTH="352"></COL> <COL WIDTH="34"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="31"> <TD WIDTH="214" HEIGHT="24" VALIGN="MIDDLE" USERM
  ATOC="Y" (목차와 연결되는 섹션 표시) 태그 목록: [('2', '독립된 감사인의 감사보고서'), ('3', '(첨부)재 무 제 표'), ('4', '재 무 상 태 표'), ('5', '손 익 계 산 서'), ('6', '자 본 변 동 표'), ('7', '현 금 흐 름 표'), ('8', '주석'), ('9', '외부감사 실시내용')]

--- 이롬넷 ---
  목차: 위치=3485바이트
    발췌: 목              차</TITLE> <P></P> <P></P> <P>독립된 감사인의 감사보고서 ----------------------------------------   재무제표   재무상태표  ---------------------------------------------------    손익계산서  ---------------------------------------------------    자본변동표 ---------------------------------------------------  </P> <P>
  ATOC="Y" (목차와 연결되는 섹션 표시) 태그 목록: [('2', '독립된 감사인의 감사보고서'), ('3', '(첨부)재 무 제 표'), ('4', '재 무 상 태 표'), ('5', '손 익 계 산 서'), ('6', '자 본 변 동 표'), ('7', '현 금 흐 름 표'), ('8', '주석'), ('9', '외부감사 실시내용')]

--- 센트비 ---
  목차: 위치=3458바이트
    발췌: 목              차</TITLE> <P></P>  <TABLE WIDTH="603" ACLASS="NORMAL" AFIXTABLE="N" BORDER="0">  <COLGROUP WIDTH="603"> <COL WIDTH="236"></COL> <COL WIDTH="275"></COL> <COL WIDTH="92"></COL> </COLGROUP>  <TBODY>  <TR ACOPY="Y" ADELETE="Y" HEIGHT="30"> <TD WIDTH="227" HEIGHT="23"></TD> <TD WIDTH="266"
  ATOC="Y" (목차와 연결되는 섹션 표시) 태그 목록: [('12', '독립된 감사인의 감사보고서'), ('10', '(첨부)재 무 제 표'), ('3', '재 무 상 태 표'), ('5', '손 익 계 산 서'), ('6', '자 본 변 동 표'), ('7', '현 금 흐 름 표'), ('2', '주석'), ('11', '외부감사 실시내용')]
```
