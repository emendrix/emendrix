# Faithfulness spot review — 2026-08-13

- **Revision** — `ea13042`
- **Judge** — `openrouter:openai/gpt-5.6-sol`
- **Sampled** — 20 of the pinned explanation subset
- **Status** — unticked. This sheet is generated empty and filled in by a person; nothing in emendrix ticks a box on its own behalf.

For each entry below: read the evidence the writer was given (the pipeline header, the two texts, and the surrounding context when there is one), read the sentences that shipped, and tick **Faithful** only if every published sentence follows from the evidence the writer was given. The header states what a structural diff established: which provision this is, what type of change it is, and which sub-provisions differ. Treat it as true. It grounds a claim about which provisions changed. It grounds no claim about what the words say: for that, only the two texts count. A sentence that reports a coordinate from the header and declines to describe it is faithful. The judge's own verdict is printed beside each entry so the two can be compared; read the evidence first.

The rubric the LLM judge was given, verbatim:

```
You are auditing one entry of a machine-generated changelog of legal texts.

You are given the BEFORE text of a provision, the AFTER text of the same provision, and the
SENTENCES that were published about the difference between them. Entries may open with a
PIPELINE HEADER block, which is what a deterministic pipeline established about the change and
showed the writer alongside the texts. Some entries also carry a SURROUNDING CONTEXT block,
which is the enclosing provision the writer was shown for reference and is not itself the
change. Judge one thing only:

    Does every published sentence follow from the evidence the writer was given?

The header states what a structural diff established: which provision this is, what type of
change it is, and which sub-provisions differ. Treat it as true. It grounds a claim about which
provisions changed. It grounds no claim about what the words say: for that, only the two texts
count. A sentence that reports a coordinate from the header and declines to describe it is
faithful.

Take the sentences one at a time and check each against the evidence. One unfaithful sentence
makes the whole entry unfaithful, and `issue` must then say which sentence, by its number.

Mark it unfaithful if any sentence:
  - states a difference the two texts do not show, or misstates one they do;
  - adds content that is in none of the texts: a date, a number, an obligation, a party;
  - gives advice, an opinion, or a prediction about consequences;
  - describes the wrong direction of a change (says something was added that was removed);
  - says what the change legally accomplishes rather than what the words changed. A narrow
    textual change restated as a broader legal conclusion is unfaithful even when the conclusion
    sounds right: "shall not be considered as fulfilling the condition in paragraph 1, point (b)"
    is not "excludes from the category", because you cannot see from these texts what else leads
    into that category;
  - claims that entries were reordered, renumbered, added or counted a certain way, unless both
    texts make it explicit. Walk the two lists and compare them item by item; a summary that
    sounds like what a text of this kind usually does is not evidence;
  - names an actor the text does not name in that role, or widens, narrows or reassigns who does
    what;
  - describes content beyond a truncation marker. A text may be cut short and the cut is marked
    in it; nothing past that marker was shown to the writer or to you, so a claim about it cannot
    be verified and is unfaithful. This includes claiming that the rest of two texts agree.

Do not mark it unfaithful for being brief, dull, incomplete, or for quoting one of the texts
verbatim: a quotation of the provision is faithful by construction. Do not mark it unfaithful for
resting on the SURROUNDING CONTEXT block: that block is part of the evidence the writer had. You
are not assessing style, usefulness or legal significance, and you are not being asked whether the
change matters.

Answer with `faithful` and, when it is false, one sentence in `issue` naming the specific
problem. If you are not sure, answer `faithful: false` and say what you could not verify.
```

---

## 1. `32024R1689@20260727` — `AR 1`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 1
HEADING: Subject matter'
IN FORCE: 2026-07-27
APPLIES FROM: unchanged by this amendment
SUB-PROVISIONS THAT DIFFER: Art. 1, Art. 1(2)(1)(g)
```

**Before**

```
Article 1
Subject matter`
1. The purpose of this Regulation is to improve the functioning of the internal market and promote the uptake of human-centric and trustworthy artificial intelligence (AI), while ensuring a high level of protection of health, safety, fundamental rights enshrined in the Charter, including democracy, the rule of law and environmental protection, against the harmful effects of AI systems in the Union and supporting innovation.
2. This Regulation lays down:
(a) harmonised rules for the placing on the market, the putting into service, and the use of AI systems in the Union;
(b) prohibitions of certain AI practices;
(c) specific requirements for high-risk AI systems and obligations for operators of such systems;
(d) harmonised transparency rules for certain AI systems;
(e) harmonised rules for the placing on the market of general-purpose AI models;
(f) rules on market monitoring, market surveillance, governance and enforcement;
(g) measures to support innovation, with a particular focus on SMEs, including start-ups.
```

**After**

```
Article 1
Subject matter'
1. The purpose of this Regulation is to improve the functioning of the internal market and promote the uptake of human-centric and trustworthy artificial intelligence (AI), while ensuring a high level of protection of health, safety, fundamental rights enshrined in the Charter, including democracy, the rule of law and environmental protection, against the harmful effects of AI systems in the Union and supporting innovation.
2. This Regulation lays down:
(a) harmonised rules for the placing on the market, the putting into service, and the use of AI systems in the Union;
(b) prohibitions of certain AI practices;
(c) specific requirements for high-risk AI systems and obligations for operators of such systems;
(d) harmonised transparency rules for certain AI systems;
(e) harmonised rules for the placing on the market of general-purpose AI models;
(f) rules on market monitoring, market surveillance, governance and enforcement;
(g) measures to support innovation, with a particular focus on small mid-cap enterprises (SMCs) and small and medium-sized enterprises (SMEs), including start-ups.
```

**Shipped sentences**

1. Point (g) of Article 1(2) now refers to measures supporting innovation with a particular focus on small mid-cap enterprises (SMCs) and small and medium-sized enterprises (SMEs), including start-ups, whereas the earlier version referred only to SMEs, including start-ups.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 2. `32024R1689@20260727` — `AR 4`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 4
HEADING: AI literacy
IN FORCE: 2026-07-27
APPLIES FROM: unchanged by this amendment
SUB-PROVISIONS THAT DIFFER: Art. 4(1), Art. 4(2), Art. 4(3)
```

**Before**

```
Article 4
AI literacy
Providers and deployers of AI systems shall take measures to ensure, to their best extent, a sufficient level of AI literacy of their staff and other persons dealing with the operation and use of AI systems on their behalf, taking into account their technical knowledge, experience, education and training and the context the AI systems are to be used in, and considering the persons or groups of persons on whom the AI systems are to be used.
```

**After**

```
Article 4
AI literacy
1. Providers and deployers of AI systems shall take measures to support the development of AI literacy of their staff and other persons dealing with the operation and use of AI systems on their behalf, taking into account their technical knowledge, experience, education and training and the context the AI systems are to be used in, and considering the persons or groups of persons on whom the AI systems are to be used. This obligation does not require providers or deployers to guarantee any specific level of AI literacy of any individual.
2. The Commission and the Member States shall support and facilitate the efforts of providers and deployers of AI systems, in particular SMEs, in fulfilling their obligation under paragraph 1 of this Article. For that purpose, the Commission shall publish practical examples of how to comply with that obligation on the single information platform referred to in Article 62(3), point (b).
3. The Board shall adopt recommendations, taking into account European competence frameworks, to support the Commission and Member States in the promotion of AI literacy required under paragraph 1, including by setting out common objectives.
```

**Shipped sentences**

1. The provision is now split into three numbered paragraphs instead of a single unnumbered paragraph, and the obligation on providers and deployers has changed from taking measures to ensure a sufficient level of AI literacy to their best extent, to taking measures to support the development of AI literacy, with an added statement that this does not require guaranteeing any specific level of AI literacy of any individual.
2. New paragraph 2 adds a role for the Commission and Member States to support and facilitate providers' and deployers' efforts, particularly for SMEs, and requires the Commission to publish practical compliance examples on a single information platform referenced in Article 62(3), point (b).
3. New paragraph 3 adds a role for the Board to adopt recommendations, informed by European competence frameworks, to support the Commission and Member States in promoting AI literacy, including by setting common objectives.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 3. `32024R1689@20260727` — `AR 6`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 6
HEADING: Classification rules for high-risk AI systems
IN FORCE: 2026-07-27
APPLIES FROM: unchanged by this amendment
SUB-PROVISIONS THAT DIFFER: Art. 6(1a), Art. 6(1b), Art. 6(1c)
```

**Before**

```
Article 6
Classification rules for high-risk AI systems
1. Irrespective of whether an AI system is placed on the market or put into service independently of the products referred to in points (a) and (b), that AI system shall be considered to be high-risk where both of the following conditions are fulfilled:
(a) the AI system is intended to be used as a safety component of a product, or the AI system is itself a product, covered by the Union harmonisation legislation listed in Annex I;
(b) the product whose safety component pursuant to point (a) is the AI system, or the AI system itself as a product, is required to undergo a third-party conformity assessment, with a view to the placing on the market or the putting into service of that product pursuant to the Union harmonisation legislation listed in Annex I.
2. In addition to the high-risk AI systems referred to in paragraph 1, AI systems referred to in Annex III shall be considered to be high-risk.
3. By derogation from paragraph 2, an AI system referred to in Annex III shall not be considered to be high-risk where it does not pose a significant risk of harm to the health, safety or fundamental rights of natural persons, including by not materially influencing the outcome of decision making.
The first subparagraph shall apply where any of the following conditions is fulfilled:
(a) the AI system is intended to perform a narrow procedural task;
(b) the AI system is intended to improve the result of a previously completed human activity;
(c) the AI system is intended to detect decision-making patterns or deviations from prior decision-making patterns and is not meant to replace or influence the previously completed human assessment, without proper human review; or
(d) the AI system is intended to perform a preparatory task to an assessment relevant for the purposes of the use cases listed in Annex III.
Notwithstanding the first subparagraph, an AI system referred to in Annex III shall always be considered to be high-risk where the AI system performs profiling of natural persons.
4. A provider who considers that an AI system referred to in Annex III is not high-risk shall document its assessment before that system is placed on the market or put into service. Such provider shall be subject to the registration obligation set out in Article 49(2). Upon request of national competent authorities, the provider shall provide the documentation of the assessment.
5. The Commission shall, after consulting the European Artificial Intelligence Board (the Board), and no later than 2 February 2026, provide guidelines specifying the practical implementation of this Article in line with Article 96 together with a comprehensive list of practical examples of use cases of AI systems that are high-risk and not high-risk.
6. The Commission is empowered to adopt delegated acts in accordance with Article 97 in order to amend paragraph 3, second subparagraph, of this Article by adding new conditions to those laid down therein, or by modifying them, where there is concrete and reliable evidence of the existence of AI systems that fall under the scope of Annex III, but do not pose a significant risk of harm to the health, safety or fundamental rights of natural persons.
7. The Commission shall adopt delegated acts in accordance with Article 97 in order to amend paragraph 3, second subparagraph, of this Article by deleting any of the conditions laid down therein, where there is concrete and reliable evidence that this is necessary to maintain the level of protection of health, safety and fundamental rights provided for by this Regulation.
8. Any amendment to the conditions laid down in paragraph 3, second subparagraph, adopted in accordance with paragraphs 6 and 7 of this Article shall not decrease the overall level of protection of health, safety and fundamental rights provided for by this Regulation and shall ensure consistency with the delegated acts adopted pursuant to Article 7(1), and take account of market and technological developments.
```

**After**

```
Article 6
Classification rules for high-risk AI systems
1. Irrespective of whether an AI system is placed on the market or put into service independently of the products referred to in points (a) and (b), that AI system shall be considered to be high-risk where both of the following conditions are fulfilled:
(a) the AI system is intended to be used as a safety component of a product, or the AI system is itself a product, covered by the Union harmonisation legislation listed in Annex I;
(b) the product whose safety component pursuant to point (a) is the AI system, or the AI system itself as a product, is required to undergo a third-party conformity assessment, with a view to the placing on the market or the putting into service of that product pursuant to the Union harmonisation legislation listed in Annex I.
1a. For the purposes of this Regulation, including paragraph 1 of this Article, AI systems that are solely used for non-safety related aspects of user assistance, performance optimisation, service efficiency, automation or convenience or quality control shall not qualify as safety components.
1b. Notwithstanding paragraph 1a, AI systems the failure or malfunctioning of which would endanger health and safety shall qualify as safety components.
1c. A product that is required to undergo a third-party conformity assessment solely due to risks other than risks to health and safety, in particular risks relating to the distribution of radio spectrum or electromagnetic interference that do not affect health and safety, shall not be considered as fulfilling the condition in paragraph 1, point (b).
2. In addition to the high-risk AI systems referred to in paragraph 1, AI systems referred to in Annex III shall be considered to be high-risk.
3. By derogation from paragraph 2, an AI system referred to in Annex III shall not be considered to be high-risk where it does not pose a significant risk of harm to the health, safety or fundamental rights of natural persons, including by not materially influencing the outcome of decision making.
The first subparagraph shall apply where any of the following conditions is fulfilled:
(a) the AI system is intended to perform a narrow procedural task;
(b) the AI system is intended to improve the result of a previously completed human activity;
(c) the AI system is intended to detect decision-making patterns or deviations from prior decision-making patterns and is not meant to replace or influence the previously completed human assessment, without proper human review; or
(d) the AI system is intended to perform a preparatory task to an assessment relevant for the purposes of the use cases listed in Annex III.
Notwithstanding the first subparagraph, an AI system referred to in Annex III shall always be considered to be high-risk where the AI system performs profiling of natural persons.
4. A provider who considers that an AI system referred to in Annex III is not high-risk shall document its assessment before that system is placed on the market or put into service. Such provider shall be subject to the registration obligation set out in Article 49(2). Upon request of national competent authorities, the provider shall provide the documentation of the assessment.
5. The Commission shall, after consulting the European Artificial Intelligence Board (the Board), and no later than 2 February 2026, provide guidelines specifying the practical implementation of this Article in line with Article 96 together with a comprehensive list of practical examples of use cases of AI systems that are high-risk and not high-risk.
6. The Commission is empowered to adopt delegated acts in accordance with Article 97 in order to amend paragraph 3, second subparagraph, of this Article by adding new conditions to those laid down therein, or by modifying them, where there is concrete and reliable evidence of the existence of AI systems that fall under the scope of Annex III, but do not pose a significant risk of harm to the health, safety or fundamental rights of natural persons.
7. The Commission shall adopt delegated acts in accordance with Article 97 in order to amend paragraph 3, second subparagraph, of this Article by deleting any of the conditions laid down therein, where there is concrete and reliable evidence that this is necessary to maintain the level of protection of health, safety and fundamental rights provided for by this Regulation.
8. Any amendment to the conditions laid down in paragraph 3, second subparagraph, adopted in accordance with paragraphs 6 and 7 of this Article shall not decrease the overall level of protection of health, safety and fundamental rights provided for by this Regulation and shall ensure consistency with the delegated acts adopted pursuant to Article 7(1), and take account of market and technological developments.
```

**Shipped sentences**

1. Three new paragraphs, 1a, 1b and 1c, have been inserted after paragraph 1.
2. Paragraph 1a states that AI systems used solely for non-safety related aspects of user assistance, performance optimisation, service efficiency, automation, convenience or quality control do not qualify as safety components, while paragraph 1b states that AI systems whose failure or malfunctioning would endanger health and safety do qualify as safety components notwithstanding paragraph 1a.
3. Paragraph 1c adds that a product required to undergo third-party conformity assessment solely because of risks other than health and safety risks, such as risks relating to radio spectrum distribution or electromagnetic interference that do not affect health and safety, is not treated as fulfilling the condition in paragraph 1, point (b); none of these three paragraphs appeared in the earlier version of Article 6.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 4. `32024R1689@20260727` — `AR 17`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 17
HEADING: Quality management system
IN FORCE: 2026-07-27
APPLIES FROM: unchanged by this amendment
SUB-PROVISIONS THAT DIFFER: Art. 17(2)(1)
```

**Before**

```
Article 17
Quality management system
1. Providers of high-risk AI systems shall put a quality management system in place that ensures compliance with this Regulation. That system shall be documented in a systematic and orderly manner in the form of written policies, procedures and instructions, and shall include at least the following aspects:
(a) a strategy for regulatory compliance, including compliance with conformity assessment procedures and procedures for the management of modifications to the high-risk AI system;
(b) techniques, procedures and systematic actions to be used for the design, design control and design verification of the high-risk AI system;
(c) techniques, procedures and systematic actions to be used for the development, quality control and quality assurance of the high-risk AI system;
(d) examination, test and validation procedures to be carried out before, during and after the development of the high-risk AI system, and the frequency with which they have to be carried out;
(e) technical specifications, including standards, to be applied and, where the relevant harmonised standards are not applied in full or do not cover all of the relevant requirements set out in Section 2, the means to be used to ensure that the high-risk AI system complies with those requirements;
(f) systems and procedures for data management, including data acquisition, data collection, data analysis, data labelling, data storage, data filtration, data mining, data aggregation, data retention and any other operation regarding the data that is performed before and for the purpose of the placing on the market or the putting into service of high-risk AI systems;
(g) the risk management system referred to in Article 9;
(h) the setting-up, implementation and maintenance of a post-market monitoring system, in accordance with Article 72;
(i) procedures related to the reporting of a serious incident in accordance with Article 73;
(j) the handling of communication with national competent authorities, other relevant authorities, including those providing or supporting the access to data, notified bodies, other operators, customers or other interested parties;
(k) systems and procedures for record-keeping of all relevant documentation and information;
(l) resource management, including security-of-supply related measures;
(m) an accountability framework setting out the responsibilities of the management and other staff with regard to all the aspects listed in this paragraph.
2. The implementation of the aspects referred to in paragraph 1 shall be proportionate to the size of the provider’s organisation. Providers shall, in any event, respect the degree of rigour and the level of protection required to ensure the compliance of their high-risk AI systems with this Regulation.
3. Providers of high-risk AI systems that are subject to obligations regarding quality management systems or an equivalent function under relevant sectoral Union law may include the aspects listed in paragraph 1 as part of the quality management systems pursuant to that law.
4. For providers that are financial institutions subject to requirements regarding their internal governance, arrangements or processes under Union financial services law, the obligation to put in place a quality management system, with the exception of paragraph 1, points (g), (h) and (i) of this Article, shall be deemed to be fulfilled by complying with the rules on internal governance arrangements or processes pursuant to the relevant Union financial services law. To that end, any harmonised standards referred to in Article 40 shall be taken into account.
```

**After**

```
Article 17
Quality management system
1. Providers of high-risk AI systems shall put a quality management system in place that ensures compliance with this Regulation. That system shall be documented in a systematic and orderly manner in the form of written policies, procedures and instructions, and shall include at least the following aspects:
(a) a strategy for regulatory compliance, including compliance with conformity assessment procedures and procedures for the management of modifications to the high-risk AI system;
(b) techniques, procedures and systematic actions to be used for the design, design control and design verification of the high-risk AI system;
(c) techniques, procedures and systematic actions to be used for the development, quality control and quality assurance of the high-risk AI system;
(d) examination, test and validation procedures to be carried out before, during and after the development of the high-risk AI system, and the frequency with which they have to be carried out;
(e) technical specifications, including standards, to be applied and, where the relevant harmonised standards are not applied in full or do not cover all of the relevant requirements set out in Section 2, the means to be used to ensure that the high-risk AI system complies with those requirements;
(f) systems and procedures for data management, including data acquisition, data collection, data analysis, data labelling, data storage, data filtration, data mining, data aggregation, data retention and any other operation regarding the data that is performed before and for the purpose of the placing on the market or the putting into service of high-risk AI systems;
(g) the risk management system referred to in Article 9;
(h) the setting-up, implementation and maintenance of a post-market monitoring system, in accordance with Article 72;
(i) procedures related to the reporting of a serious incident in accordance with Article 73;
(j) the handling of communication with national competent authorities, other relevant authorities, including those providing or supporting the access to data, notified bodies, other operators, customers or other interested parties;
(k) systems and procedures for record-keeping of all relevant documentation and information;
(l) resource management, including security-of-supply related measures;
(m) an accountability framework setting out the responsibilities of the management and other staff with regard to all the aspects listed in this paragraph.
2. The implementation of the aspects referred to in paragraph 1 shall be proportionate to the size of the provider’s organisation, in particular, if the provider is an SME, including a start-up, or an SMC. Providers shall, in any event, respect the degree of rigour and the level of protection required to ensure the compliance of their high-risk AI systems with this Regulation.
3. Providers of high-risk AI systems that are subject to obligations regarding quality management systems or an equivalent function under relevant sectoral Union law may include the aspects listed in paragraph 1 as part of the quality management systems pursuant to that law.
4. For providers that are financial institutions subject to requirements regarding their internal governance, arrangements or processes under Union financial services law, the obligation to put in place a quality management system, with the exception of paragraph 1, points (g), (h) and (i) of this Article, shall be deemed to be fulfilled by complying with the rules on internal governance arrangements or processes pursuant to the relevant Union financial services law. To that end, any harmonised standards referred to in Article 40 shall be taken into account.
```

**Shipped sentences**

1. Paragraph 2 now adds a clause stating that the proportionality of implementation to the size of the provider's organisation applies in particular if the provider is an SME, including a start-up, or an SMC.
2. The earlier version of paragraph 2 referred only to proportionality based on organisation size without this additional specification.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 5. `32024R1689@20260727` — `AR 27`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 27
HEADING: Fundamental rights impact assessment for high-risk AI systems
IN FORCE: 2026-07-27
APPLIES FROM: unchanged by this amendment
SUB-PROVISIONS THAT DIFFER: Art. 27(4)(1), Art. 27(5)(1)
```

**Before**

```
Article 27
Fundamental rights impact assessment for high-risk AI systems
1. Prior to deploying a high-risk AI system referred to in Article 6(2), with the exception of high-risk AI systems intended to be used in the area listed in point 2 of Annex III, deployers that are bodies governed by public law, or are private entities providing public services, and deployers of high-risk AI systems referred to in points 5 (b) and (c) of Annex III, shall perform an assessment of the impact on fundamental rights that the use of such system may produce. For that purpose, deployers shall perform an assessment consisting of:
(a) a description of the deployer’s processes in which the high-risk AI system will be used in line with its intended purpose;
(b) a description of the period of time within which, and the frequency with which, each high-risk AI system is intended to be used;
(c) the categories of natural persons and groups likely to be affected by its use in the specific context;
(d) the specific risks of harm likely to have an impact on the categories of natural persons or groups of persons identified pursuant to point (c) of this paragraph, taking into account the information given by the provider pursuant to Article 13;
(e) a description of the implementation of human oversight measures, according to the instructions for use;
(f) the measures to be taken in the case of the materialisation of those risks, including the arrangements for internal governance and complaint mechanisms.
2. The obligation laid down in paragraph 1 applies to the first use of the high-risk AI system. The deployer may, in similar cases, rely on previously conducted fundamental rights impact assessments or existing impact assessments carried out by provider. If, during the use of the high-risk AI system, the deployer considers that any of the elements listed in paragraph 1 has changed or is no longer up to date, the deployer shall take the necessary steps to update the information.
3. Once the assessment referred to in paragraph 1 of this Article has been performed, the deployer shall notify the market surveillance authority of its results, submitting the filled-out template referred to in paragraph 5 of this Article as part of the notification. In the case referred to in Article 46(1), deployers may be exempt from that obligation to notify.
4. If any of the obligations laid down in this Article is already met through the data protection impact assessment conducted pursuant to Article 35 of Regulation (EU) 2016/679 or Article 27 of Directive (EU) 2016/680, the fundamental rights impact assessment referred to in paragraph 1 of this Article shall complement that data protection impact assessment.
5. The AI Office shall develop a template for a questionnaire, including through an automated tool, to facilitate deployers in complying with their obligations under this Article in a simplified manner.
```

**After**

```
Article 27
Fundamental rights impact assessment for high-risk AI systems
1. Prior to deploying a high-risk AI system referred to in Article 6(2), with the exception of high-risk AI systems intended to be used in the area listed in point 2 of Annex III, deployers that are bodies governed by public law, or are private entities providing public services, and deployers of high-risk AI systems referred to in points 5 (b) and (c) of Annex III, shall perform an assessment of the impact on fundamental rights that the use of such system may produce. For that purpose, deployers shall perform an assessment consisting of:
(a) a description of the deployer’s processes in which the high-risk AI system will be used in line with its intended purpose;
(b) a description of the period of time within which, and the frequency with which, each high-risk AI system is intended to be used;
(c) the categories of natural persons and groups likely to be affected by its use in the specific context;
(d) the specific risks of harm likely to have an impact on the categories of natural persons or groups of persons identified pursuant to point (c) of this paragraph, taking into account the information given by the provider pursuant to Article 13;
(e) a description of the implementation of human oversight measures, according to the instructions for use;
(f) the measures to be taken in the case of the materialisation of those risks, including the arrangements for internal governance and complaint mechanisms.
2. The obligation laid down in paragraph 1 applies to the first use of the high-risk AI system. The deployer may, in similar cases, rely on previously conducted fundamental rights impact assessments or existing impact assessments carried out by provider. If, during the use of the high-risk AI system, the deployer considers that any of the elements listed in paragraph 1 has changed or is no longer up to date, the deployer shall take the necessary steps to update the information.
3. Once the assessment referred to in paragraph 1 of this Article has been performed, the deployer shall notify the market surveillance authority of its results, submitting the filled-out template referred to in paragraph 5 of this Article as part of the notification. In the case referred to in Article 46(1), deployers may be exempt from that obligation to notify.
4. If any of the obligations laid down in this Article is already met through the data protection impact assessment conducted pursuant to Article 35 of Regulation (EU) 2016/679 or Article 27 of Directive (EU) 2016/680, the deployer may, when conducting the fundamental rights impact assessment referred to in paragraph 1 of this Article, include cross-references to the relevant sections of that data protection impact assessment or include relevant parts thereof in the fundamental rights impact assessment.
5. The AI Office shall develop a template for a questionnaire, including through an automated tool, to facilitate deployers in complying with their obligations under this Article in a simplified manner. This template shall, where relevant, give deployers the possibility to include cross-references to the relevant sections of the data protection impact assessment or include relevant parts thereof in the fundamental rights impact assessment pursuant to paragraph 4.
```

**Shipped sentences**

1. Paragraph 4 no longer states that the fundamental rights impact assessment shall complement an existing data protection impact assessment, and instead provides that the deployer may include cross-references to relevant sections of that data protection impact assessment or incorporate relevant parts of it into the fundamental rights impact assessment.
2. Paragraph 5 gains an added sentence stating that the AI Office's template shall, where relevant, give deployers the possibility to include such cross-references or incorporate such parts as described in paragraph 4.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 6. `32024R1689@20260727` — `AR 30`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=false` — Sentence 2 misstates the amendment by saying categories may be moved; the text authorizes moving only a code or type of AI system from one category to another.

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 30
HEADING: Notification procedure
IN FORCE: 2026-07-27
APPLIES FROM: unchanged by this amendment
SUB-PROVISIONS THAT DIFFER: Art. 30(2)(1), Art. 30(2)(2)
```

**Before**

```
Article 30
Notification procedure
1. Notifying authorities may notify only conformity assessment bodies which have satisfied the requirements laid down in Article 31.
2. Notifying authorities shall notify the Commission and the other Member States, using the electronic notification tool developed and managed by the Commission, of each conformity assessment body referred to in paragraph 1.
3. The notification referred to in paragraph 2 of this Article shall include full details of the conformity assessment activities, the conformity assessment module or modules, the types of AI systems concerned, and the relevant attestation of competence. Where a notification is not based on an accreditation certificate as referred to in Article 29(2), the notifying authority shall provide the Commission and the other Member States with documentary evidence which attests to the competence of the conformity assessment body and to the arrangements in place to ensure that that body will be monitored regularly and will continue to satisfy the requirements laid down in Article 31.
4. The conformity assessment body concerned may perform the activities of a notified body only where no objections are raised by the Commission or the other Member States within two weeks of a notification by a notifying authority where it includes an accreditation certificate referred to in Article 29(2), or within two months of a notification by the notifying authority where it includes documentary evidence referred to in Article 29(3).
5. Where objections are raised, the Commission shall, without delay, enter into consultations with the relevant Member States and the conformity assessment body. In view thereof, the Commission shall decide whether the authorisation is justified. The Commission shall address its decision to the Member State concerned and to the relevant conformity assessment body.
```

**After**

```
Article 30
Notification procedure
1. Notifying authorities may notify only conformity assessment bodies which have satisfied the requirements laid down in Article 31.
2. Notifying authorities shall notify the Commission and the other Member States, based on the list of codes, categories, and corresponding types of AI systems referred to in Annex XIV, and using the electronic notification tool developed and managed by the Commission, of each conformity assessment body referred to in paragraph 1.
The Commission is empowered to adopt delegated acts in accordance with Article 97 in order to amend Annex XIV, in light of technical progress, advances in knowledge or new scientific evidence by adding to the list of codes, categories, and corresponding types of AI systems a new code, a category or a type of AI system, withdrawing an existing code, category or a type of AI system from that list or moving a code or type of AI system from one category to another.
3. The notification referred to in paragraph 2 of this Article shall include full details of the conformity assessment activities, the conformity assessment module or modules, the types of AI systems concerned, and the relevant attestation of competence. Where a notification is not based on an accreditation certificate as referred to in Article 29(2), the notifying authority shall provide the Commission and the other Member States with documentary evidence which attests to the competence of the conformity assessment body and to the arrangements in place to ensure that that body will be monitored regularly and will continue to satisfy the requirements laid down in Article 31.
4. The conformity assessment body concerned may perform the activities of a notified body only where no objections are raised by the Commission or the other Member States within two weeks of a notification by a notifying authority where it includes an accreditation certificate referred to in Article 29(2), or within two months of a notification by the notifying authority where it includes documentary evidence referred to in Article 29(3).
5. Where objections are raised, the Commission shall, without delay, enter into consultations with the relevant Member States and the conformity assessment body. In view thereof, the Commission shall decide whether the authorisation is justified. The Commission shall address its decision to the Member State concerned and to the relevant conformity assessment body.
```

**Shipped sentences**

1. Paragraph 2 now requires that notifications to the Commission and other Member States be based on the list of codes, categories, and corresponding types of AI systems referred to in Annex XIV, whereas the earlier text contained no such reference.
2. A new second subparagraph has been added to paragraph 2 empowering the Commission to adopt delegated acts under Article 97 to amend Annex XIV by adding, withdrawing, or moving codes, categories, or types of AI systems on that list.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 7. `32024R1689@20260727` — `AR 43`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=false` — Sentence 3 misstates the new third-party-assessment sentence: the text says manufacturers need not choose third-party assessment only because the product includes a high-risk AI system as a safety component (where the applicable Union legislation does not require it), not solely because of the system's Article 6(1) classification.

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 43
HEADING: Conformity assessment
IN FORCE: 2026-07-27
APPLIES FROM: unknown (the text changed beyond its dates, so no date that moved can be read as the application date)
DATES ADDED: 2028-01-28
SUB-PROVISIONS THAT DIFFER: Art. 43(3)(1), Art. 43(3)(2), Art. 43(3)(3), Art. 43(3)(4)
```

**Before**

```
Article 43
Conformity assessment
1. For high-risk AI systems listed in point 1 of Annex III, where, in demonstrating the compliance of a high-risk AI system with the requirements set out in Section 2, the provider has applied harmonised standards referred to in Article 40, or, where applicable, common specifications referred to in Article 41, the provider shall opt for one of the following conformity assessment procedures based on:
(a) the internal control referred to in Annex VI; or
(b) the assessment of the quality management system and the assessment of the technical documentation, with the involvement of a notified body, referred to in Annex VII.
In demonstrating the compliance of a high-risk AI system with the requirements set out in Section 2, the provider shall follow the conformity assessment procedure set out in Annex VII where:
(a) harmonised standards referred to in Article 40 do not exist, and common specifications referred to in Article 41 are not available;
(b) the provider has not applied, or has applied only part of, the harmonised standard;
(c) the common specifications referred to in point (a) exist, but the provider has not applied them;
(d) one or more of the harmonised standards referred to in point (a) has been published with a restriction, and only on the part of the standard that was restricted.
For the purposes of the conformity assessment procedure referred to in Annex VII, the provider may choose any of the notified bodies. However, where the high-risk AI system is intended to be put into service by law enforcement, immigration or asylum authorities or by Union institutions, bodies, offices or agencies, the market surveillance authority referred to in Article 74(8) or (9), as applicable, shall act as a notified body.
2. For high-risk AI systems referred to in points 2 to 8 of Annex III, providers shall follow the conformity assessment procedure based on internal control as referred to in Annex VI, which does not provide for the involvement of a notified body.
3. For high-risk AI systems covered by the Union harmonisation legislation listed in Section A of Annex I, the provider shall follow the relevant conformity assessment procedure as required under those legal acts. The requirements set out in Section 2 of this Chapter shall apply to those high-risk AI systems and shall be part of that assessment. Points 4.3., 4.4., 4.5. and the fifth paragraph of point 4.6 of Annex VII shall also apply.
For the purposes of that assessment, notified bodies which have been notified under those legal acts shall be entitled to control the conformity of the high-risk AI systems with the requirements set out in Section 2, provided that the compliance of those notified bodies with requirements laid down in Article 31(4), (5), (10) and (11) has been assessed in the context of the notification procedure under those legal acts.
Where a legal act listed in Section A of Annex I enables the product manufacturer to opt out from a third-party conformity assessment, provided that that manufacturer has applied all harmonised standards covering all the relevant requirements, that manufacturer may use that option only if it has also applied harmonised standards or, where applicable, common specifications referred to in Article 41, covering all requirements set out in Section 2 of this Chapter.
4. High-risk AI systems that have already been subject to a conformity assessment procedure shall undergo a new conformity assessment procedure in the event of a substantial modification, regardless of whether the modified system is intended to be further distributed or continues to be used by the current deployer.
For high-risk AI systems that continue to learn after being placed on the market or put into service, changes to the high-risk AI system and its performance that have been pre-determined by the provider at the moment of the initial conformity assessment and are part of the information contained in the technical documentation referred to in point 2(f) of Annex IV, shall not constitute a substantial modification.
5. The Commission is empowered to adopt delegated acts in accordance with Article 97 in order to amend Annexes VI and VII by updating them in light of technical progress.
6. The Commission is empowered to adopt delegated acts in accordance with Article 97 in order to amend paragraphs 1 and 2 of this Article in order to subject high-risk AI systems referred to in points 2 to 8 of Annex III to the conformity assessment procedure referred to in Annex VII or parts thereof. The Commission shall adopt such delegated acts taking into account the effectiveness of the conformity assessment procedure based on internal control referred to in Annex VI in preventing or minimising the risks to health and safety and protection of fundamental rights posed by such systems, as well as the availability of adequate capacities and resources among notified bodies.
```

**After**

```
Article 43
Conformity assessment
1. For high-risk AI systems listed in point 1 of Annex III, where, in demonstrating the compliance of a high-risk AI system with the requirements set out in Section 2, the provider has applied harmonised standards referred to in Article 40, or, where applicable, common specifications referred to in Article 41, the provider shall opt for one of the following conformity assessment procedures based on:
(a) the internal control referred to in Annex VI; or
(b) the assessment of the quality management system and the assessment of the technical documentation, with the involvement of a notified body, referred to in Annex VII.
In demonstrating the compliance of a high-risk AI system with the requirements set out in Section 2, the provider shall follow the conformity assessment procedure set out in Annex VII where:
(a) harmonised standards referred to in Article 40 do not exist, and common specifications referred to in Article 41 are not available;
(b) the provider has not applied, or has applied only part of, the harmonised standard;
(c) the common specifications referred to in point (a) exist, but the provider has not applied them;
(d) one or more of the harmonised standards referred to in point (a) has been published with a restriction, and only on the part of the standard that was restricted.
For the purposes of the conformity assessment procedure referred to in Annex VII, the provider may choose any of the notified bodies. However, where the high-risk AI system is intended to be put into service by law enforcement, immigration or asylum authorities or by Union institutions, bodies, offices or agencies, the market surveillance authority referred to in Article 74(8) or (9), as applicable, shall act as a notified body.
2. For high-risk AI systems referred to in points 2 to 8 of Annex III, providers shall follow the conformity assessment procedure based on internal control as referred to in Annex VI, which does not provide for the involvement of a notified body.
3. For high-risk AI systems covered by the Union harmonisation legislation listed in Section A of Annex I, the provider of the system shall follow the relevant conformity assessment procedure as required in accordance with the relevant Union harmonisation legislation. The requirements set out in Section 2 of this Chapter shall apply to those high-risk AI systems and shall be part of that assessment. Assessment of the quality management system set out in Article 17 shall also be undertaken, and points 3, 4.3, 4.4. and 4.5, the fifth paragraph of point 4.6 and point 5 of Annex VII shall apply.
For the purposes of that conformity assessment, notified bodies which have been notified under the Union harmonisation legislation listed in Section A of Annex I shall have the power to assess the conformity of high-risk AI systems with the requirements set out in Section 2 of this Chapter, provided that the compliance of those notified bodies with the requirements laid down in Article 31(4), (5), (10) and (11) has been assessed in the context of the notification procedure in accordance with the relevant Union harmonisation legislation, which is evidenced through the assessment as part of the existing notification. Without prejudice to Article 28, such notified bodies which have been notified under the Union harmonisation legislation in Section A of Annex I, shall apply for designation in accordance with Section 4 of this Chapter by 28 January 2028.
Where Union harmonisation legislation listed in Section A of Annex I provides the product manufacturer with an option to rely on a conformity assessment that does not involve a third-party, provided that that manufacturer has applied harmonised standards to ensure compliance with all the relevant requirements, that manufacturer may use that option only if it has also applied harmonised standards or, where applicable, common specifications referred to in Article 41, covering all requirements set out in Section 2 of this Chapter. The classification of a product as a high-risk AI system in accordance with Article 6(1) does not affect the choice of the conformity assessment procedure provided to the manufacturers of products covered by Union harmonisation legislation listed in Section A of Annex I, including, where applicable, an option to rely on harmonised standards. The manufacturers of such products are not required to choose a conformity assessment procedure involving third-party conformity assessment only because the product includes a high-risk AI system as a safety component, if this is not required by the Union harmonisation legislation listed in Section A of Annex I.
Where a high-risk AI system is both covered by the Union harmonisation legislation listed in Section A of Annex I and it falls within one of the categories listed in Annex III, the provider of that system shall follow the relevant conformity assessment procedure as required pursuant to the relevant Union harmonisation legislation listed in Section A of Annex I.
4. High-risk AI systems that have already been subject to a conformity assessment procedure shall undergo a new conformity assessment procedure in the event of a substantial modification, regardless of whether the modified system is intended to be further distributed or continues to be used by the current deployer.
For high-risk AI systems that continue to learn after being placed on the market or put into service, changes to the high-risk AI system and its performance that have been pre-determined by the provider at the moment of the initial conformity assessment and are part of the information contained in the technical documentation referred to in point 2(f) of Annex IV, shall not constitute a substantial modification.
5. The Commission is empowered to adopt delegated acts in accordance with Article 97 in order to amend Annexes VI and VII by updating them in light of technical progress.
6. The Commission is empowered to adopt delegated acts in accordance with Article 97 in order to amend paragraphs 1 and 2 of this Article in order to subject high-risk AI systems referred to in points 2 to 8 of Annex III to the conformity assessment procedure referred to in Annex VII or parts thereof. The Commission shall adopt such delegated acts taking into account the effectiveness of the conformity assessment procedure based on internal control referred to in Annex VI in preventing or minimising the risks to health and safety and protection of fundamental rights posed by such systems, as well as the availability of adequate capacities and resources among notified bodies.
```

**Shipped sentences**

1. Paragraph 3 now adds a mandatory quality management system assessment under Article 17 and expands the list of applicable Annex VII points to include point 3 and point 5 in addition to the previously cited 4.3, 4.4, 4.5 and the fifth paragraph of 4.6.
2. The provision on notified bodies now states that their compliance evidencing occurs through assessment as part of the existing notification, and it adds a requirement that such notified bodies apply for designation under Section 4 of the Chapter by 28 January 2028, a sentence absent from the earlier text.
3. The paragraph also adds new sentences clarifying that classification as a high-risk AI system under Article 6(1) does not affect the conformity assessment procedure choice available to manufacturers under Union harmonisation legislation, that such manufacturers are not required to use third-party assessment solely because of that classification, and a new closing sentence addressing systems that are both covered by Section A of Annex I and fall within an Annex III category.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 8. `32024R1689@20260727` — `AR 57`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 57
HEADING: AI regulatory sandboxes
IN FORCE: 2026-07-27
APPLIES FROM: unknown (the text changed beyond its dates, so no date that moved can be read as the application date)
DATES REMOVED: 2026-08-02
DATES ADDED: 2027-08-02
SUB-PROVISIONS THAT DIFFER: Art. 57(1)(1), Art. 57(3)(1), Art. 57(3a), Art. 57(5)(1), Art. 57(9)(1)(e), Art. 57(10)(1), Art. 57(14)(1)
```

**Before**

```
Article 57
AI regulatory sandboxes
1. Member States shall ensure that their competent authorities establish at least one AI regulatory sandbox at national level, which shall be operational by 2 August 2026. That sandbox may also be established jointly with the competent authorities of other Member States. The Commission may provide technical support, advice and tools for the establishment and operation of AI regulatory sandboxes.
The obligation under the first subparagraph may also be fulfilled by participating in an existing sandbox in so far as that participation provides an equivalent level of national coverage for the participating Member States.
2. Additional AI regulatory sandboxes at regional or local level, or established jointly with the competent authorities of other Member States may also be established.
3. The European Data Protection Supervisor may also establish an AI regulatory sandbox for Union institutions, bodies, offices and agencies, and may exercise the roles and the tasks of national competent authorities in accordance with this Chapter.
4. Member States shall ensure that the competent authorities referred to in paragraphs 1 and 2 allocate sufficient resources to comply with this Article effectively and in a timely manner. Where appropriate, national competent authorities shall cooperate with other relevant authorities, and may allow for the involvement of other actors within the AI ecosystem. This Article shall not affect other regulatory sandboxes established under Union or national law. Member States shall ensure an appropriate level of cooperation between the authorities supervising those other sandboxes and the national competent authorities.
5. AI regulatory sandboxes established under paragraph 1 shall provide for a controlled environment that fosters innovation and facilitates the development, training, testing and validation of innovative AI systems for a limited time before their being placed on the market or put into service pursuant to a specific sandbox plan agreed between the providers or prospective providers and the competent authority. Such sandboxes may include testing in real world conditions supervised therein.
6. Competent authorities shall provide, as appropriate, guidance, supervision and support within the AI regulatory sandbox with a view to identifying risks, in particular to fundamental rights, health and safety, testing, mitigation measures, and their effectiveness in relation to the obligations and requirements of this Regulation and, where relevant, other Union and national law supervised within the sandbox.
7. Competent authorities shall provide providers and prospective providers participating in the AI regulatory sandbox with guidance on regulatory expectations and how to fulfil the requirements and obligations set out in this Regulation.
Upon request of the provider or prospective provider of the AI system, the competent authority shall provide a written proof of the activities successfully carried out in the sandbox. The competent authority shall also provide an exit report detailing the activities carried out in the sandbox and the related results and learning outcomes. Providers may use such documentation to demonstrate their compliance with this Regulation through the conformity assessment process or relevant market surveillance activities. In this regard, the exit reports and the written proof provided by the national competent authority shall be taken positively into account by market surveillance authorities and notified bodies, with a view to accelerating conformity assessment procedures to a reasonable extent.
8. Subject to the confidentiality provisions in Article 78, and with the agreement of the provider or prospective provider, the Commission and the Board shall be authorised to access the exit reports and shall take them into account, as appropriate, when exercising their tasks under this Regulation. If both the provider or prospective provider and the national competent authority explicitly agree, the exit report may be made publicly available through the single information platform referred to in this Article.
9. The establishment of AI regulatory sandboxes shall aim to contribute to the following objectives:
(a) improving legal certainty to achieve regulatory compliance with this Regulation or, where relevant, other applicable Union and national law;
(b) supporting the sharing of best practices through cooperation with the authorities involved in the AI regulatory sandbox;
(c) fostering innovation and competitiveness and facilitating the development of an AI ecosystem;
(d) contributing to evidence-based regulatory learning;
(e) facilitating and accelerating access to the Union market for AI systems, in particular when provided by SMEs, including start-ups.
10. National competent authorities shall ensure that, to the extent the innovative AI systems involve the processing of personal data or otherwise fall under the supervisory remit of other national authorities or competent authorities providing or supporting access to data, the national data protection authorities and those other national or competent authorities are associated with the operation of the AI regulatory sandbox and involved in the supervision of those aspects to the extent of their respective tasks and powers.
11. The AI regulatory sandboxes shall not affect the supervisory or corrective powers of the competent authorities supervising the sandboxes, including at regional or local level. Any significant risks to health and safety and fundamental rights identified during the development and testing of such AI systems shall result in an adequate mitigation. National competent authorities shall have the power to temporarily or permanently suspend the testing process, or the participation in the sandbox if no effective mitigation is possible, and shall inform the AI Office of such decision. National competent authorities shall exercise their supervisory powers within the limits of the relevant law, using their discretionary powers when implementing legal provisions in respect of a specific AI regulatory sandbox project, with the objective of supporting innovation in AI in the Union.
12. Providers and prospective providers participating in the AI regulatory sandbox shall remain liable under applicable Union and national liability law for any damage inflicted on third parties as a result of the experimentation taking place in the sandbox. However, provided that the prospective providers observe the specific plan and the terms and conditions for their participation and follow in good faith the guidance given by the national competent authority, no administrative fines shall be imposed by the authorities for infringements of this Regulation. Where other competent authorities responsible for other Union and national law were actively involved in the supervision of the AI system in the sandbox and provided guidance for compliance, no administrative fines shall be imposed regarding that law.
13. The AI regulatory sandboxes shall be designed and implemented in such a way that, where relevant, they facilitate cross-border cooperation between national competent authorities.
14. National competent authorities shall coordinate their activities and cooperate within the framework of the Board.
15. National competent authorities shall inform the AI Office and the Board of the establishment of a sandbox, and may ask them for support and guidance. The AI Office shall make publicly available a list of planned and existing sandboxes and keep it up to date in order to encourage more interaction in the AI regulatory sandboxes and cross-border cooperation.
16. National competent authorities shall submit annual reports to the AI Office and to the Board, from one year after the establishment of the AI regulatory sandbox and every year thereafter until its termination, and a final report. Those reports shall provide information on the progress and results of the implementation of those sandboxes, including best practices, incidents, lessons learnt and recommendations on their setup and, where relevant, on the application and possible revision of this Regulation, including its delegated and implementing acts, and on the application of other Union law supervised by the competent authorities within the sandbox. The national competent authorities shall make those annual reports or abstracts thereof available to the public, online. The Commission shall, where appropriate, take the annual reports into account when exercising its tasks under this Regulation.
17. The Commission shall develop a single and dedicated interface containing all relevant information related to AI regulatory sandboxes to allow stakeholders to interact with AI regulatory sandboxes and to raise enquiries with competent authorities, and to seek non-binding guidance on the conformity of innovative products, services, business models embedding AI technologies, in accordance with Article 62(1), point (c). The Commission shall proactively coordinate with national competent authorities, where relevant.
```

**After**

```
Article 57
AI regulatory sandboxes
1. Member States shall ensure that their competent authorities establish at least one AI regulatory sandbox at national level, which shall be operational by 2 August 2027. That sandbox may also be established jointly with the competent authorities of other Member States. The Commission may provide technical support, advice and tools for the establishment and operation of AI regulatory sandboxes.
The obligation under the first subparagraph may also be fulfilled by participating in an existing sandbox in so far as that participation provides an equivalent level of national coverage for the participating Member States.
2. Additional AI regulatory sandboxes at regional or local level, or established jointly with the competent authorities of other Member States may also be established.
3. The European Data Protection Supervisor may establish an AI regulatory sandbox for Union institutions, bodies, offices and agencies. For this purpose, references to national competent authorities in this Chapter shall be construed as references to the European Data Protection Supervisor.
3a. The AI Office may establish an AI regulatory sandbox at Union level for AI systems covered by Article 75(1). For this purpose, references to national competent authorities in this Chapter shall be construed, where relevant, as references to the AI Office. That AI regulatory sandbox shall be implemented in close cooperation with relevant competent authorities, in particular where compliance with Union legislation other than this Regulation is supervised in the AI regulatory sandbox, and shall provide priority access to SMEs, including start-ups, and SMCs.
The establishment of a Union level AI regulatory sandbox by the AI Office shall be without prejudice to the competences of Member States to establish and supervise AI regulatory sandboxes for AI systems under their supervision.
4. Member States shall ensure that the competent authorities referred to in paragraphs 1 and 2 allocate sufficient resources to comply with this Article effectively and in a timely manner. Where appropriate, national competent authorities shall cooperate with other relevant authorities, and may allow for the involvement of other actors within the AI ecosystem. This Article shall not affect other regulatory sandboxes established under Union or national law. Member States shall ensure an appropriate level of cooperation between the authorities supervising those other sandboxes and the national competent authorities.
5. AI regulatory sandboxes established under this Article shall provide for a controlled environment that fosters innovation and facilitates the development, training, testing and validation of innovative AI systems for a limited time before their being placed on the market or put into service pursuant to a specific sandbox plan agreed between the providers or prospective providers and the competent authorities, ensuring that appropriate safeguards are in place. Such sandboxes may include testing in real world conditions supervised therein. Where applicable, the sandbox plan shall incorporate the real-world testing plan referred to in Articles 60 and 60a.
6. Competent authorities shall provide, as appropriate, guidance, supervision and support within the AI regulatory sandbox with a view to identifying risks, in particular to fundamental rights, health and safety, testing, mitigation measures, and their effectiveness in relation to the obligations and requirements of this Regulation and, where relevant, other Union and national law supervised within the sandbox.
7. Competent authorities shall provide providers and prospective providers participating in the AI regulatory sandbox with guidance on regulatory expectations and how to fulfil the requirements and obligations set out in this Regulation.
Upon request of the provider or prospective provider of the AI system, the competent authority shall provide a written proof of the activities successfully carried out in the sandbox. The competent authority shall also provide an exit report detailing the activities carried out in the sandbox and the related results and learning outcomes. Providers may use such documentation to demonstrate their compliance with this Regulation through the conformity assessment process or relevant market surveillance activities. In this regard, the exit reports and the written proof provided by the national competent authority shall be taken positively into account by market surveillance authorities and notified bodies, with a view to accelerating conformity assessment procedures to a reasonable extent.
8. Subject to the confidentiality provisions in Article 78, and with the agreement of the provider or prospective provider, the Commission and the Board shall be authorised to access the exit reports and shall take them into account, as appropriate, when exercising their tasks under this Regulation. If both the provider or prospective provider and the national competent authority explicitly agree, the exit report may be made publicly available through the single information platform referred to in this Article.
9. The establishment of AI regulatory sandboxes shall aim to contribute to the following objectives:
(a) improving legal certainty to achieve regulatory compliance with this Regulation or, where relevant, other applicable Union and national law;
(b) supporting the sharing of best practices through cooperation with the authorities involved in the AI regulatory sandbox;
(c) fostering innovation and competitiveness and facilitating the development of an AI ecosystem;
(d) contributing to evidence-based regulatory learning;
(e) facilitating and accelerating access to the Union market for AI systems, in particular when provided by SMEs, including start-ups, and SMCs.
10. National competent authorities shall ensure that, to the extent the innovative AI systems involve the processing of personal data or otherwise fall under the supervisory remit of other national authorities or competent authorities providing or supporting access to data, the competent data protection authorities and those other national or competent authorities are associated with the operation of the AI regulatory sandbox and involved in the supervision of those aspects to the extent of their respective tasks and powers.
11. The AI regulatory sandboxes shall not affect the supervisory or corrective powers of the competent authorities supervising the sandboxes, including at regional or local level. Any significant risks to health and safety and fundamental rights identified during the development and testing of such AI systems shall result in an adequate mitigation. National competent authorities shall have the power to temporarily or permanently suspend the testing process, or the participation in the sandbox if no effective mitigation is possible, and shall inform the AI Office of such decision. National competent authorities shall exercise their supervisory powers within the limits of the relevant law, using their discretionary powers when implementing legal provisions in respect of a specific AI regulatory sandbox project, with the objective of supporting innovation in AI in the Union.
12. Providers and prospective providers participating in the AI regulatory sandbox shall remain liable under applicable Union and national liability law for any damage inflicted on third parties as a result of the experimentation taking place in the sandbox. However, provided that the prospective providers observe the specific plan and the terms and conditions for their participation and follow in good faith the guidance given by the national competent authority, no administrative fines shall be imposed by the authorities for infringements of this Regulation. Where other competent authorities responsible for other Union and national law were actively involved in the supervision of the AI system in the sandbox and provided guidance for compliance, no administrative fines shall be imposed regarding that law.
13. The AI regulatory sandboxes shall be designed and implemented in such a way that, where relevant, they facilitate cross-border cooperation between national competent authorities.
14. National competent authorities, the European Data Protection Supervisor and the AI Office, shall, as appropriate and within their respective competences, coordinate their activities and cooperate within the framework of the Board. They may support the joint establishment and operation of AI regulatory sandboxes, including in different sectors, and exchange best practices on related matters.
15. National competent authorities shall inform the AI Office and the Board of the establishment of a sandbox, and may ask them for support and guidance. The AI Office shall make publicly available a list of planned and existing sandboxes and keep it up to date in order to encourage more interaction in the AI regulatory sandboxes and cross-border cooperation.
16. National competent authorities shall submit annual reports to the AI Office and to the Board, from one year after the establishment of the AI regulatory sandbox and every year thereafter until its termination, and a final report. Those reports shall provide information on the progress and results of the implementation of those sandboxes, including best practices, incidents, lessons learnt and recommendations on their setup and, where relevant, on the application and possible revision of this Regulation, including its delegated and implementing acts, and on the application of other Union law supervised by the competent authorities within the sandbox. The national competent authorities shall make those annual reports or abstracts thereof available to the public, online. The Commission shall, where appropriate, take the annual reports into account when exercising its tasks under this Regulation.
17. The Commission shall develop a single and dedicated interface containing all relevant information related to AI regulatory sandboxes to allow stakeholders to interact with AI regulatory sandboxes and to raise enquiries with competent authorities, and to seek non-binding guidance on the conformity of innovative products, services, business models embedding AI technologies, in accordance with Article 62(1), point (c). The Commission shall proactively coordinate with national competent authorities, where relevant.
```

**Shipped sentences**

1. The deadline for Member States to have an operational national AI regulatory sandbox is moved from 2 August 2026 to 2 August 2027.
2. Paragraph 3 changes the European Data Protection Supervisor's role from an option to also exercise national competent authority roles and tasks to establishing a sandbox with references to national competent authorities construed as references to it, and a new paragraph 3a is added allowing the AI Office to establish a Union-level sandbox for AI systems covered by Article 75(1), with priority access for SMEs, including start-ups, and SMCs, and without prejudice to Member States' sandbox competences.
3. Paragraph 5 adds a reference to safeguards being in place and to incorporating a real-world testing plan referenced in Articles 60 and 60a, paragraph 9(e) and paragraph 14 now also mention SMCs and add the European Data Protection Supervisor and AI Office as coordinating actors with the Board, including support for joint sandbox establishment and best-practice exchange, and paragraph 10 changes "national data protection authorities" to "competent data protection authorities."

- [ ] Faithful
- [ ] Not faithful — reason: 

## 9. `32024R1689@20260727` — `AR 60a`

- Change type: `INSERTED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): INSERTED — this provision is new in the later version.
PROVISION: Art. 60a
HEADING: Testing of high-risk AI systems covered by Union harmonisation legislation listed in Section B of Annex I in real-world conditions outside AI regulatory sandboxes
IN FORCE: 2026-07-27
APPLIES FROM: unknown (an inserted provision states its own application date only in prose)
```

**Before** — none (this side of the change does not exist).

**After**

```
Article 60a
Testing of high-risk AI systems covered by Union harmonisation legislation listed in Section B of Annex I in real-world conditions outside AI regulatory sandboxes
1. Member States may allow, in accordance with this Article, the testing of high-risk AI systems in real world conditions outside AI regulatory sandboxes by providers or prospective providers of AI enabled products covered by the Union harmonisation legislation listed in Section B of Annex I, with a view to assessing and verifying the conformity of those systems with the requirements laid down in Articles 8 to 15.
2. Member States that choose to allow testing as referred to in paragraph 1 shall, individually or jointly, adopt frameworks for real-world testing.
3. Each Member State shall notify the Commission of any real-world testing framework it adopts before implementing it. This shall not affect the competences of the Commission under the Union harmonisation legislation listed in Section B of Annex I.
4. Member States that have adopted real-world testing frameworks shall ensure that the relevant national competent authorities, relevant authorities and public authorities responsible for the management and operation of infrastructure and products covered by Union harmonisation legislation listed in Section B of Annex I cooperate closely with each other in good faith and remove any practical obstacles, including on procedural rules providing access to physical public infrastructure, where this is necessary, to successfully implement those real-world testing frameworks and test AI-enabled products covered by Union harmonisation legislation listed in Section B of Annex I.
5. The frameworks for real-world testing shall lay down the requirements under which testing in real-world conditions shall occur. Those frameworks shall:
(a) include the provision of a mandatory real-world testing plan to be agreed between the provider or prospective provider and the national competent authority or relevant authority in accordance with the Union harmonisation legislation listed in Section B of Annex I;
(b) ensure compliance with the requirements laid down in Article 60(2), (3), (4)(d)-(j) and (5)-(9), where any reference to market surveillance authorities in those provisions shall be read as a reference to the national competent authority or relevant authority, as appropriate in accordance with the Union harmonisation legislation listed in Section B of Annex I;
(c) include effective governance and accountability arrangements;
(d) ensure a high level of protection of health safety and fundamental rights.
6. The real-world testing shall comply with the applicable provisions laid down in the Union harmonisation legislation listed in Section B of Annex I. Any requirements laid down in those provisions shall not affect the application of this Article to the extent necessary to enable the testing referred to in paragraph 1.
```

**Shipped sentences**

1. A new Article 60a is added, allowing Member States to permit providers or prospective providers of AI-enabled products covered by the Union harmonisation legislation listed in Section B of Annex I to test high-risk AI systems in real-world conditions outside AI regulatory sandboxes, aimed at assessing and verifying conformity with the requirements in Articles 8 to 15.
2. The provision sets out obligations for Member States choosing to allow such testing, including adopting and notifying real-world testing frameworks to the Commission, ensuring cooperation between relevant authorities, and requiring those frameworks to include a mandatory testing plan, compliance with specified parts of Article 60, governance and accountability arrangements, and a high level of protection for health, safety and fundamental rights.
3. It further states that the real-world testing must comply with applicable provisions of the Union harmonisation legislation listed in Section B of Annex I, and that requirements in those provisions do not affect the application of this Article to the extent necessary to enable the testing described.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 10. `32024R1689@20260727` — `AR 69`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=false` — Sentence 1 misstates the before text by saying the listed objectives were described as being set out in the Article 68(1) implementing act; the text instead said those objectives were to be taken into account when setting out the fee and recoverable-cost arrangements.

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 69
HEADING: Access to the pool of experts by the Member States
IN FORCE: 2026-07-27
APPLIES FROM: unchanged by this amendment
SUB-PROVISIONS THAT DIFFER: Art. 69(2)(1)
```

**Before**

```
Article 69
Access to the pool of experts by the Member States
1. Member States may call upon experts of the scientific panel to support their enforcement activities under this Regulation.
2. The Member States may be required to pay fees for the advice and support provided by the experts. The structure and the level of fees as well as the scale and structure of recoverable costs shall be set out in the implementing act referred to in Article 68(1), taking into account the objectives of the adequate implementation of this Regulation, cost-effectiveness and the necessity of ensuring effective access to experts for all Member States.
3. The Commission shall facilitate timely access to the experts by the Member States, as needed, and ensure that the combination of support activities carried out by Union AI testing support pursuant to Article 84 and experts pursuant to this Article is efficiently organised and provides the best possible added value.
```

**After**

```
Article 69
Access to the pool of experts by the Member States
1. Member States may call upon experts of the scientific panel to support their enforcement activities under this Regulation.
2. The Member States may be required to pay fees for the advice and support provided by the experts at a rate equivalent to the remuneration fees applicable to the Commission pursuant to the implementing act referred to in Article 68(1).
3. The Commission shall facilitate timely access to the experts by the Member States, as needed, and ensure that the combination of support activities carried out by Union AI testing support pursuant to Article 84 and experts pursuant to this Article is efficiently organised and provides the best possible added value.
```

**Shipped sentences**

1. Paragraph 2 no longer describes the structure and level of fees, the scale and structure of recoverable costs, or the listed objectives of adequate implementation, cost-effectiveness and ensuring effective access for all Member States as being set out in the Article 68(1) implementing act.
2. Instead, the fees Member States may be required to pay are described as being at a rate equivalent to the remuneration fees applicable to the Commission under that same implementing act referred to in Article 68(1).

- [ ] Faithful
- [ ] Not faithful — reason: 

## 11. `32024R1689@20260727` — `AR 72`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 72
HEADING: Post-market monitoring by providers and post-market monitoring plan for high-risk AI systems
IN FORCE: 2026-07-27
APPLIES FROM: unknown (the text changed beyond its dates, so no date that moved can be read as the application date)
DATES REMOVED: 2026-02-02
DATES ADDED: 2027-09-02
SUB-PROVISIONS THAT DIFFER: Art. 72(3)(1)
```

**Before**

```
Article 72
Post-market monitoring by providers and post-market monitoring plan for high-risk AI systems
1. Providers shall establish and document a post-market monitoring system in a manner that is proportionate to the nature of the AI technologies and the risks of the high-risk AI system.
2. The post-market monitoring system shall actively and systematically collect, document and analyse relevant data which may be provided by deployers or which may be collected through other sources on the performance of high-risk AI systems throughout their lifetime, and which allow the provider to evaluate the continuous compliance of AI systems with the requirements set out in Chapter III, Section 2. Where relevant, post-market monitoring shall include an analysis of the interaction with other AI systems. This obligation shall not cover sensitive operational data of deployers which are law-enforcement authorities.
3. The post-market monitoring system shall be based on a post-market monitoring plan. The post-market monitoring plan shall be part of the technical documentation referred to in Annex IV. The Commission shall adopt an implementing act laying down detailed provisions establishing a template for the post-market monitoring plan and the list of elements to be included in the plan by 2 February 2026. That implementing act shall be adopted in accordance with the examination procedure referred to in Article 98(2).
4. For high-risk AI systems covered by the Union harmonisation legislation listed in Section A of Annex I, where a post-market monitoring system and plan are already established under that legislation, in order to ensure consistency, avoid duplications and minimise additional burdens, providers shall have a choice of integrating, as appropriate, the necessary elements described in paragraphs 1, 2 and 3 using the template referred in paragraph 3 into systems and plans already existing under that legislation, provided that it achieves an equivalent level of protection.
The first subparagraph of this paragraph shall also apply to high-risk AI systems referred to in point 5 of Annex III placed on the market or put into service by financial institutions that are subject to requirements under Union financial services law regarding their internal governance, arrangements or processes.
```

**After**

```
Article 72
Post-market monitoring by providers and post-market monitoring plan for high-risk AI systems
1. Providers shall establish and document a post-market monitoring system in a manner that is proportionate to the nature of the AI technologies and the risks of the high-risk AI system.
2. The post-market monitoring system shall actively and systematically collect, document and analyse relevant data which may be provided by deployers or which may be collected through other sources on the performance of high-risk AI systems throughout their lifetime, and which allow the provider to evaluate the continuous compliance of AI systems with the requirements set out in Chapter III, Section 2. Where relevant, post-market monitoring shall include an analysis of the interaction with other AI systems. This obligation shall not cover sensitive operational data of deployers which are law-enforcement authorities.
3. The post-market monitoring system shall be based on a post-market monitoring plan. The post-market monitoring plan shall be part of the technical documentation referred to in Annex IV. The Commission, taking utmost account of the opinion of the Board, shall adopt guidance, including a template, on the post-market monitoring plan by 2 September 2027.
4. For high-risk AI systems covered by the Union harmonisation legislation listed in Section A of Annex I, where a post-market monitoring system and plan are already established under that legislation, in order to ensure consistency, avoid duplications and minimise additional burdens, providers shall have a choice of integrating, as appropriate, the necessary elements described in paragraphs 1, 2 and 3 using the template referred in paragraph 3 into systems and plans already existing under that legislation, provided that it achieves an equivalent level of protection.
The first subparagraph of this paragraph shall also apply to high-risk AI systems referred to in point 5 of Annex III placed on the market or put into service by financial institutions that are subject to requirements under Union financial services law regarding their internal governance, arrangements or processes.
```

**Shipped sentences**

1. Paragraph 3 changes the Commission's mandated action from adopting an implementing act laying down a template and list of elements for the post-market monitoring plan, via the examination procedure under Article 98(2), to adopting guidance, including a template, on the plan, this time taking utmost account of the Board's opinion.
2. The deadline for this action moved from 2 February 2026 to 2 September 2027.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 12. `32024R1689@20260727` — `AR 75b`

- Change type: `INSERTED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): INSERTED — this provision is new in the later version.
PROVISION: Art. 75b
HEADING: Commitments
IN FORCE: 2026-07-27
APPLIES FROM: unknown (an inserted provision states its own application date only in prose)
```

**Before** — none (this side of the change does not exist).

**After**

```
Article 75b
Commitments
If, during proceedings under Article 75a(2), the operator concerned offers commitments to ensure compliance with the relevant provisions of this Regulation, the AI Office may, by decision, make those commitments binding on the operator concerned and declare that there are no further grounds for action. The AI Office may, upon request or on its own initiative, reopen the proceedings where:
(a) there has been a material change in any of the facts on which the decision was based;
(b) the operator acts contrary to its commitments; or
(c) the decision was based on incomplete, incorrect or misleading information provided by the operator concerned.
Where the AI Office considers that the commitments offered by the operator concerned are unable to ensure effective compliance with the relevant provisions of this Regulation, it shall reject those commitments in a reasoned decision when concluding the proceedings.
```

**Shipped sentences**

1. Article 75b is a newly added provision allowing the AI Office to make binding, by decision, commitments offered by an operator during proceedings under Article 75a(2), while declaring that no further grounds for action exist.
2. It also sets out that the AI Office may reopen such proceedings on request or on its own initiative in cases of material change in the underlying facts, non-compliance with the commitments, or reliance on incomplete, incorrect or misleading information, and requires a reasoned decision rejecting commitments found unable to ensure effective compliance.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 13. `32024R1689@20260727` — `AR 76`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=false` — Sentence 2 is unfaithful because paragraph 2 is not textually identical in the displayed versions (including changed spacing), and the pipeline header expressly identifies Article 76(2) as differing.

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 76
HEADING: Supervision of testing in real world conditions by market surveillance authorities
IN FORCE: 2026-07-27
APPLIES FROM: unchanged by this amendment
SUB-PROVISIONS THAT DIFFER: Art. 76(1)(2)
```

**Before**

```
Article 76
Supervision of testing in real world conditions by market surveillance authorities
1. Market surveillance authorities shall have competences and powers to ensure that testing in real world conditions is in accordance with this Regulation.
2. Where testing in real world conditions is conducted for AI systems that are supervised within an AI regulatory sandbox under Article 58, the market surveillance authorities shall verify the compliance with Article 60 as part of their supervisory role for the AI regulatory sandbox. Those authorities may, as appropriate, allow the testing in real world conditions to be conducted by the provider or prospective provider, in derogation from the conditions set out in Article 60(4), points (f) and (g).
3. Where a market surveillance authority has been informed by the prospective provider, the provider or any third party of a serious incident or has other grounds for considering that the conditions set out in Articles 60 and 61 are not met, it may take either of the following decisions on its territory, as appropriate:
(a) to suspend or terminate the testing in real world conditions;
(b) to require the provider or prospective provider and the deployer or prospective deployer to modify any aspect of the testing in real world conditions.
4. Where a market surveillance authority has taken a decision referred to in paragraph 3 of this Article, or has issued an objection within the meaning of Article 60(4), point (b), the decision or the objection shall indicate the grounds therefor and how the provider or prospective provider can challenge the decision or objection.
5. Where applicable, where a market surveillance authority has taken a decision referred to in paragraph 3, it shall communicate the grounds therefor to the market surveillance authorities of other Member States in which the AI system has been tested in accordance with the testing plan.
```

**After**

```
Article 76
Supervision of testing in real world conditions by market surveillance authorities
1. Market surveillance authorities shall have competences and powers to ensure that testing in real world conditions is in accordance with this Regulation.
Where testing in real world conditions is based on Article 60a, any reference to a market surveillance authority in this Article shall be construed as a reference to the national competent authority or appropriate authority under the Union harmonisation legislation listed in Section B of Annex I, and references to Article 60 shall be construed as references to Article 60a, as appropriate.
2. Where testing in real world conditions is conducted for AI systems that are supervised within an AI regulatory sandbox under Article 58, the market surveillance authorities shall verify the compliance with Article 60 as part of their supervisory role for the AI regulatory sandbox. Those authorities may, as appropriate, allow the testing in real world conditions to be conducted by the provider or prospective provider, in derogation from the conditions set out in Article 60(4), points (f) and (g).
3. Where a market surveillance authority has been informed by the prospective provider, the provider or any third party of a serious incident or has other grounds for considering that the conditions set out in Articles 60 and 61 are not met, it may take either of the following decisions on its territory, as appropriate:
(a) to suspend or terminate the testing in real world conditions;
(b) to require the provider or prospective provider and the deployer or prospective deployer to modify any aspect of the testing in real world conditions.
4. Where a market surveillance authority has taken a decision referred to in paragraph 3 of this Article, or has issued an objection within the meaning of Article 60(4), point (b), the decision or the objection shall indicate the grounds therefor and how the provider or prospective provider can challenge the decision or objection.
5. Where applicable, where a market surveillance authority has taken a decision referred to in paragraph 3, it shall communicate the grounds therefor to the market surveillance authorities of other Member States in which the AI system has been tested in accordance with the testing plan.
```

**Shipped sentences**

1. A new paragraph is added to paragraph 1 stating that where testing in real world conditions is based on Article 60a, any reference to a market surveillance authority in Article 76 is to be read as a reference to the national competent authority or appropriate authority under the Union harmonisation legislation listed in Section B of Annex I, and references to Article 60 are to be read as references to Article 60a, as appropriate.
2. Paragraphs 2 through 5 remain textually unchanged between the two versions.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 14. `32024R1689@20260727` — `AR 96`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 96
HEADING: Guidelines from the Commission on the implementation of this Regulation
IN FORCE: 2026-07-27
APPLIES FROM: unknown (the text changed beyond its dates, so no date that moved can be read as the application date)
DATES ADDED: 2027-08-01
SUB-PROVISIONS THAT DIFFER: Art. 96(1)(1)(a), Art. 96(1)(1)(f), Art. 96(1)(1)(g), Art. 96(1)(2)
```

**Before**

```
Article 96
Guidelines from the Commission on the implementation of this Regulation
1. The Commission shall develop guidelines on the practical implementation of this Regulation, and in particular on:
(a) the application of the requirements and obligations referred to in Articles 8 to 15 and in Article 25;
(b) the prohibited practices referred to in Article 5;
(c) the practical implementation of the provisions related to substantial modification;
(d) the practical implementation of transparency obligations laid down in Article 50;
(e) detailed information on the relationship of this Regulation with the Union harmonisation legislation listed in Annex I, as well as with other relevant Union law, including as regards consistency in their enforcement;
(f) the application of the definition of an AI system as set out in Article 3, point (1).
When issuing such guidelines, the Commission shall pay particular attention to the needs of SMEs including start-ups, of local public authorities and of the sectors most likely to be affected by this Regulation.
The guidelines referred to in the first subparagraph of this paragraph shall take due account of the generally acknowledged state of the art on AI, as well as of relevant harmonised standards and common specifications that are referred to in Articles 40 and 41, or of those harmonised standards or technical specifications that are set out pursuant to Union harmonisation law.
2. At the request of the Member States or the AI Office, or on its own initiative, the Commission shall update guidelines previously adopted when deemed necessary.
```

**After**

```
Article 96
Guidelines from the Commission on the implementation of this Regulation
1. The Commission shall develop guidelines on the practical implementation of this Regulation, and in particular on:
(a) the application of the requirements and obligations referred to in Articles 8 to 15 and in Articles 25 and 26;
(b) the prohibited practices referred to in Article 5;
(c) the practical implementation of the provisions related to substantial modification;
(d) the practical implementation of transparency obligations laid down in Article 50;
(e) detailed information on the relationship of this Regulation with the Union harmonisation legislation listed in Annex I, as well as with other relevant Union law, including as regards consistency in their enforcement;
(f) the application of the definition of an AI system as set out in Article 3, point (1);
(g) the practical implementation of Article 8(2), Article 9(10) and Article 17(3) in accordance with the principle of complementarity and proportionality, with a view to ensuring consistency, avoiding duplication and minimising additional burdens when complying with the requirements of this Regulation and the requirements of the Union harmonisation legislation listed in Section A of Annex I; such guidelines shall be published by 1 August 2027.
When issuing such guidelines, the Commission shall involve the Board and pay particular attention to the needs of SMEs, including start-ups, and SMCs, of local public authorities and of the sectors most likely to be affected by this Regulation.
The guidelines referred to in the first subparagraph of this paragraph shall take due account of the generally acknowledged state of the art on AI, as well as of relevant harmonised standards and common specifications that are referred to in Articles 40 and 41, or of those harmonised standards or technical specifications that are set out pursuant to Union harmonisation law.
2. At the request of the Member States or the AI Office, or on its own initiative, the Commission shall update guidelines previously adopted when deemed necessary.
```

**Shipped sentences**

1. Point (a) now refers to Articles 25 and 26 instead of only Article 25, and a new point (g) has been added addressing the practical implementation of Article 8(2), Article 9(10) and Article 17(3) in line with complementarity and proportionality.
2. The paragraph on issuing guidelines now also states that the Commission shall involve the Board and adds SMCs alongside SMEs and start-ups as groups whose needs receive particular attention.
3. such guidelines shall be published by 1 August 2027

- [ ] Faithful
- [ ] Not faithful — reason: 

## 15. `32024R1689@20260727` — `AR 111`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 111
HEADING: AI systems already placed on the market or put into service and general-purpose AI models already placed on the marked
IN FORCE: 2026-07-27
APPLIES FROM: unknown (the text changed beyond its dates, so no date that moved can be read as the application date)
DATES ADDED: 2026-12-02
SUB-PROVISIONS THAT DIFFER: Art. 111(2)(1), Art. 111(4)
```

**Before**

```
Article 111
AI systems already placed on the market or put into service and general-purpose AI models already placed on the marked
1. Without prejudice to the application of Article 5 as referred to in Article 113(3), point (a), AI systems which are components of the large-scale IT systems established by the legal acts listed in Annex X that have been placed on the market or put into service before 2 August 2027 shall be brought into compliance with this Regulation by 31 December 2030.
The requirements laid down in this Regulation shall be taken into account in the evaluation of each large-scale IT system established by the legal acts listed in Annex X to be undertaken as provided for in those legal acts and where those legal acts are replaced or amended.
2. Without prejudice to the application of Article 5 as referred to in Article 113(3), point (a), this Regulation shall apply to operators of high-risk AI systems, other than the systems referred to in paragraph 1 of this Article, that have been placed on the market or put into service before 2 August 2026, only if, as from that date, those systems are subject to significant changes in their designs. In any case, the providers and deployers of high-risk AI systems intended to be used by public authorities shall take the necessary steps to comply with the requirements and obligations of this Regulation by 2 August 2030.
3. Providers of general-purpose AI models that have been placed on the market before 2 August 2025 shall take the necessary steps in order to comply with the obligations laid down in this Regulation by 2 August 2027.
```

**After**

```
Article 111
AI systems already placed on the market or put into service and general-purpose AI models already placed on the marked
1. Without prejudice to the application of Article 5 as referred to in Article 113(3), point (a), AI systems which are components of the large-scale IT systems established by the legal acts listed in Annex X that have been placed on the market or put into service before 2 August 2027 shall be brought into compliance with this Regulation by 31 December 2030.
The requirements laid down in this Regulation shall be taken into account in the evaluation of each large-scale IT system established by the legal acts listed in Annex X to be undertaken as provided for in those legal acts and where those legal acts are replaced or amended.
2. Without prejudice to the application of Article 5 as referred to in Article 113, third paragraph, point (a), this Regulation shall apply to operators of high-risk AI systems, other than the systems referred to in paragraph 1 of this Article, that have been placed on the market or put into service before the date of application of Chapter III referred to in Article 113, only if, as from that date, those systems are subject to significant changes in their designs. In any case, the providers and deployers of high-risk AI systems intended to be used by public authorities shall take the necessary steps to comply with the requirements and obligations laid down in this Regulation by 2 August 2030.
3. Providers of general-purpose AI models that have been placed on the market before 2 August 2025 shall take the necessary steps in order to comply with the obligations laid down in this Regulation by 2 August 2027.
4. Providers of AI systems, including general-purpose AI systems, generating synthetic audio, image, video or text content, that have been placed on the market before 2 August 2026 shall take the necessary steps in order to comply with Article 50(2) by 2 December 2026.
```

**Shipped sentences**

1. In paragraph 2, the cross-reference to Article 113(3), point (a) was changed to Article 113, third paragraph, point (a), and the fixed date of 2 August 2026 was replaced with a reference to the date of application of Chapter III as set out in Article 113.
2. A new paragraph 4 was added requiring providers of AI systems, including general-purpose AI systems, that generate synthetic audio, image, video or text content and were placed on the market before 2 August 2026 to take steps to comply with Article 50(2) by 2 December 2026.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 16. `32024R1689@20260727` — `AN VIII`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Annex VIII
HEADING: Information to be submitted upon the registration of high-risk AI systems in accordance with Article 49
IN FORCE: 2026-07-27
APPLIES FROM: unchanged by this amendment
SUB-PROVISIONS THAT DIFFER: Annex VIII section B(8)
```

**Before**

```
ANNEX VIII
Information to be submitted upon the registration of high-risk AI systems in accordance with Article 49
Section A — Information to be submitted by providers of high-risk AI systems in accordance with Article 49(1)
The following information shall be provided and thereafter kept up to date with regard to high-risk AI systems to be registered in accordance with Article 49(1):
1. The name, address and contact details of the provider;
2. Where submission of information is carried out by another person on behalf of the provider, the name, address and contact details of that person;
3. The name, address and contact details of the authorised representative, where applicable;
4. The AI system trade name and any additional unambiguous reference allowing the identification and traceability of the AI system;
5. A description of the intended purpose of the AI system and of the components and functions supported through this AI system;
6. A basic and concise description of the information used by the system (data, inputs) and its operating logic;
7. The status of the AI system (on the market, or in service; no longer placed on the market/in service, recalled);
8. The type, number and expiry date of the certificate issued by the notified body and the name or identification number of that notified body, where applicable;
9. A scanned copy of the certificate referred to in point 8, where applicable;
10. Any Member States in which the AI system has been placed on the market, put into service or made available in the Union;
11. A copy of the EU declaration of conformity referred to in Article 47;
12. Electronic instructions for use; this information shall not be provided for high-risk AI systems in the areas of law enforcement or migration, asylum and border control management referred to in Annex III, points 1, 6 and 7;
13. A URL for additional information (optional).
Section B — Information to be submitted by providers of high-risk AI systems in accordance with Article 49(2)
The following information shall be provided and thereafter kept up to date with regard to AI systems to be registered in accordance with Article 49(2):
1. The name, address and contact details of the provider;
2. Where submission of information is carried out by another person on behalf of the provider, the name, address and contact details of that person;
3. The name, address and contact details of the authorised representative, where applicable;
4. The AI system trade name and any additional unambiguous reference allowing the identification and traceability of the AI system;
5. A description of the intended purpose of the AI system;
6. The condition or conditions under Article 6(3)based on which the AI system is considered to be not-high-risk;
7. A short summary of the grounds on which the AI system is considered to be not-high-risk in application of the procedure under Article 6(3);
8. The status of the AI system (on the market, or in service; no longer placed on the market/in service, recalled);
9. Any Member States in which the AI system has been placed on the market, put into service or made available in the Union.
Section C — Information to be submitted by deployers of high-risk AI systems in accordance with Article 49(3)
The following information shall be provided and thereafter kept up to date with regard to high-risk AI systems to be registered in accordance with Article 49(3):
1. The name, address and contact details of the deployer;
2. The name, address and contact details of the person submitting information on behalf of the deployer;
3. The URL of the entry of the AI system in the EU database by its provider;
4. A summary of the findings of the fundamental rights impact assessment conducted in accordance with Article 27;
5. A summary of the data protection impact assessment carried out in accordance with Article 35 of Regulation (EU) 2016/679 or Article 27 of Directive (EU) 2016/680 as specified in Article 26(8) of this Regulation, where applicable.
```

**After**

```
ANNEX VIII
Information to be submitted upon the registration of high-risk AI systems in accordance with Article 49
Section A — Information to be submitted by providers of high-risk AI systems in accordance with Article 49(1)
The following information shall be provided and thereafter kept up to date with regard to high-risk AI systems to be registered in accordance with Article 49(1):
1. The name, address and contact details of the provider;
2. Where submission of information is carried out by another person on behalf of the provider, the name, address and contact details of that person;
3. The name, address and contact details of the authorised representative, where applicable;
4. The AI system trade name and any additional unambiguous reference allowing the identification and traceability of the AI system;
5. A description of the intended purpose of the AI system and of the components and functions supported through this AI system;
6. A basic and concise description of the information used by the system (data, inputs) and its operating logic;
7. The status of the AI system (on the market, or in service; no longer placed on the market/in service, recalled);
8. The type, number and expiry date of the certificate issued by the notified body and the name or identification number of that notified body, where applicable;
9. A scanned copy of the certificate referred to in point 8, where applicable;
10. Any Member States in which the AI system has been placed on the market, put into service or made available in the Union;
11. A copy of the EU declaration of conformity referred to in Article 47;
12. Electronic instructions for use; this information shall not be provided for high-risk AI systems in the areas of law enforcement or migration, asylum and border control management referred to in Annex III, points 1, 6 and 7;
13. A URL for additional information (optional).
Section B — Information to be submitted by providers of high-risk AI systems in accordance with Article 49(2)
The following information shall be provided and thereafter kept up to date with regard to AI systems to be registered in accordance with Article 49(2):
1. The name, address and contact details of the provider;
2. Where submission of information is carried out by another person on behalf of the provider, the name, address and contact details of that person;
3. The name, address and contact details of the authorised representative, where applicable;
4. The AI system trade name and any additional unambiguous reference allowing the identification and traceability of the AI system;
5. A description of the intended purpose of the AI system;
6. The condition or conditions under Article 6(3)based on which the AI system is considered to be not-high-risk;
7. A short summary of the grounds on which the AI system is considered to be not-high-risk in application of the procedure under Article 6(3);
8. The status of the AI system (on the market, or in service; no longer placed on the market/in service, recalled).
9. Any Member States in which the AI system has been placed on the market, put into service or made available in the Union.
Section C — Information to be submitted by deployers of high-risk AI systems in accordance with Article 49(3)
The following information shall be provided and thereafter kept up to date with regard to high-risk AI systems to be registered in accordance with Article 49(3):
1. The name, address and contact details of the deployer;
2. The name, address and contact details of the person submitting information on behalf of the deployer;
3. The URL of the entry of the AI system in the EU database by its provider;
4. A summary of the findings of the fundamental rights impact assessment conducted in accordance with Article 27;
5. A summary of the data protection impact assessment carried out in accordance with Article 35 of Regulation (EU) 2016/679 or Article 27 of Directive (EU) 2016/680 as specified in Article 26(8) of this Regulation, where applicable.
```

**Shipped sentences**

1. In Section B, point 8 now ends with a full stop instead of a semicolon, a purely formal punctuation change with no wording or substantive difference.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 17. `32006R1907@20081012` — `AN IV`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Annex IV
HEADING: ANNEX IV
IN FORCE: not stated
APPLIES FROM: unchanged by this amendment
SUB-PROVISIONS THAT DIFFER: Annex IV
NOTE: the independent signals disagree about this change; it ships marked disputed. Explain the texts as given and do not comment on the disagreement.
```

**Before**

```
ANNEX IV
EXEMPTIONS FROM THE OBLIGATION TO REGISTER IN ACCORDANCE WITH ARTICLE 2(7)(a)
EINECS No Name/group CAS No
200-061-5 D-glucitol C6H14O6 50-70-4
200-066-2 Ascorbic acid C6H8O6 50-81-7
200-075-1 Glucose C6H12O6 50-99-7
200-294-2 L-lysine C6H14N2O2 56-87-1
200-312-9 Palmitic acid, pure C16H32O2 57-10-3
200-313-4 Stearic acid, pure C18H36O2 57-11-4
200-334-9 Sucrose, pure C12H22O11 57-50-1
200-405-4 α-tocopheryl acetate C31H52O3 58-95-7
200-432-1 DL-methionine C5H11NO2S 59-51-8
200-711-8 D-mannitol C6H14O6 69-65-8
201-771-8 1-sorbose C6H12O6 87-79-6
204-007-1 Oleic acid, pure C18H34O2 112-80-1
204-664-4 Glycerol stearate, pure C21H42O4 123-94-4
204-696-9 Carbon dioxide CO2 124-38-9
205-278-9 Calcium pantothenate, D-form C9H17NO5.1/2Ca 137-08-6
205-582-1 Lauric acid, pure C12H24O2 143-07-7
205-590-5 Potassium oleate C18H34O2K 143-18-0
205-756-7 DL-phenylalanine C9H11NO2 150-30-1
208-407-7 Sodium gluconate C6H12O7.Na 527-07-1
212-490-5 Sodium stearate, pure C18H36O2.Na 822-16-2
215-279-6 Limestone
A noncombustible solid characteristic of sedimentary rock. It consists primarily of calcium carbonate 1317-65-3
215-665-4 Sorbitan oleate C24H44O6 1338-43-8
216-472-8 Calcium distearate, pure C18H36O2.1/2Ca 1592-23-0
231-147-0 Argon Ar 7440-37-1
231-153-3 Carbon C 7440-44-0
231-783-9 Nitrogen N2 7727-37-9
231-791-2 Water, distilled, conductivity or of similar purity H2O 7732-18-5
231-955-3 Graphite C 7782-42-5
232-273-9 Sunflower oil
Extractives and their physically modified derivatives. It consists primarily of the glycerides of the fatty acids linoleic, and oleic. (Helianthus annuus, Compositae). 8001-21-6
232-274-4 Soybean oil
Extractives and their physically modified derivatives. It consists primarily of the glycerides of the fatty acids linoleic, oleic, palmitic and stearic (Soja hispida, Leguminosae). 8001-22-7
232-276-5 Safflower oil
Extractives and their physically modified derivatives. It consists primarily of the glycerides of the fatty acid linoleic (Carthamus tinctorius, Compositae). 8001-23-8
232-278-6 Linseed oil
Extractives and their physically modified derivatives. It consists primarily of the glycerides of the fatty acids linoleic, linolenic and oleic (Linum usitatissimum, Linaceae). 8001-26-1
232-281-2 Corn oil
Extractives and their physically modified derivatives. It consists primarily of the glycerides of the fatty acids linoleic, oleic, palmitic and stearic. (Zea mays, Gramineae). 8001-30-7
232-293-8 Castor Oil
Extractives and their physically modified derivatives. It consists primarily of the glycerides of the fatty acid ricinoleic (Ricinus communis, Euphorbiaceae). 8001-79-4
232-299-0 Rape oil
Extractives and their physically modified derivatives. It consists primarily of the glycerides of the fatty acids erucic, linoleic and oleic (Brassica napus, Cruciferae). 8002-13-9
232-307-2 Lecithins
The complex combination of diglycerides of fatty acids linked to the choline ester of phosphoric acid. 8002-43-5
232-436-4 Syrups, hydrolyzed starch
A complex combination obtained by the hydrolysis of cornstarch by the action of acids or enzymes. It consists primarily of d-glucose, maltose and maltodextrins. 8029-43-4
232-442-7 Tallow, hydrogenated 8030-12-4
232-675-4 Dextrin 9004-53-9
232-679-6 Starch
High-polymeric carbohydrate material usually derived form cereal grains such as corn, wheat and sorghum, and from roots and tubers such as potatoes and tapioca. Includes starch which has been pregelatinised by heating in the presence of water. 9005-25-8
232-940-4 Maltodextrin 9050-36-6
234-328-2 Vitamin A 11103-57-4
238-976-7 Sodium D-gluconate C6H12O7.xNa 14906-97-9
248-027-9 D-glucitol monostearate C24H48O7 26836-47-5
262-988-1 Fatty acids, coco, Me esters 61788-59-8
262-989-7 Fatty acids, tallow, Me esters 61788-61-2
263-060-9 Fatty acids, castor-oil 61789-44-4
263-129-3 Fatty acids, tallow 61790-37-2
265-995-8 Cellulose Pulp 65996-61-4
266-925-9 Fatty acids, C12-18
This substance is identified by SDA Substance Name: C12-C18 alkyl carboxylic acid and SDA Reporting No: 16-005-00. 67701-01-3
266-928-5 Fatty acids C16-18
This substance is identified by SDA Substance Name: C16-C18 alkyl carboxylic acid and SDA Reporting No: 19-005-00. 67701-03-5
266-929-0 Fatty acids, C8-18 and C18-unsaturated
This substance is identified by SDA Substance Name: C8-C18 and C18 unsaturated alkyl carboxylic acid and SDA Reporting No: 01-005-00. 67701-05-7
266-930-6 Fatty acids, C14-18 and C16-18-unsaturated
This substance is identified by SDA Substance Name: C14-C18 and C16-C18unsaturated alkyl carboxylic acid and SDA Reporting No: 04-005-00. 67701-06-8
266-932-7 Fatty acids, C16-C18 and C18-unsaturated
This substance is identified by SDA Substance Name: C16-C18 and C18 unsaturated alkyl carboxylic acid and SDA Reporting No: 11-005-00. 67701-08-0
266-948-4 Glycerides, C16-18 and C18-unsaturated
This substance is identified by SDA Substance Name: C16-C18 and C18 unsaturated trialkyl glyceride and SDA Reporting No: 11-001-00. 67701-30-8
267-007-0 Fatty acids, C14-18 and C16-18-unsaturated., Me esters
This substance is identified by SDA Substance Name: C14-C18 and C16-C18 unsaturated alkyl carboxylic acid methyl ester and SDA Reporting No: 04-010-00. 67762-26-9
267-013-3 Fatty acids, C6-12
This substance is identified by SDA Substance Name: C6-C12 alkyl carboxylic acid and SDA Reporting No: 13-005-00. 67762-36-1
268-099-5 Fatty acids, C14-22 and C16-22 unsaturated
This substance is identified by SDA Substance Name: C14-C22 and C16-C22 unsaturated alkyl carboxylic acid and SDA Reporting No: 07-005-00. 68002-85-7
268-616-4 Syrups, corn, dehydrated 68131-37-3
269-657-0 Fatty acids, soya 68308-53-2
269-658-6 Glycerides, tallow mono-, di- and tri-, hydrogenated 68308-54-3
270-298-7 Fatty acids, C14-22 68424-37-3
270-304-8 Fatty acids, linseed-oil 68424-45-3
270-312-1 Glycerides, C16-18 and C18-unsaturated. mono- and di-
This substance is identified by SDA Substance Name: C16-C18 and C18 unsaturated alkyl and C16-C18 and C18 unsaturated dialkyl glyceride and SDA Reporting No: 11-002-00. 68424-61-3
288-123-8 Glycerides, C10-18 85665-33-4
292-771-7 Fatty acids, C12-14 90990-10-6
292-776-4 Fatty acids, C12-18 and C18-unsaturated 90990-15-1
296-916-5 Fatty acids, rape-oil, erucic acid-low 93165-31-2
```

**After**

```
ANNEX IV
EXEMPTIONS FROM THE OBLIGATION TO REGISTER IN ACCORDANCE WITH ARTICLE 2(7)(a)
Einecs No Name/Group CAS No
200-061-5 D-glucitol C6H14O6 50-70-4
200-066-2 Ascorbic acid C6H8O6 50-81-7
200-075-1 Glucose C6H12O6 50-99-7
200-233-3 Fructose C6H12O6 57-48-7
200-294-2 L-lysine C6H14N2O2 56-87-1
200-334-9 Sucrose, pure C12H22O11 57-50-1
200-405-4 α-tocopheryl acetate C31H52O3 58-95-7
200-416-4 Galactose C6H12O6 59-23-4
200-432-1 DL-methionine C5H11NO2S 59-51-8
200-559-2 Lactose C12H22O11 63-42-3
200-711-8 D-mannitol C6H14O6 69-65-8
201-771-8 L-sorbose C6H12O6 87-79-6
204-664-4 Glycerol stearate, pure C21H42O4 123-94-4
204-696-9 Carbon dioxide CO2 124-38-9
205-278-9 Calcium pantothenate, D-form C9H17NO5.1/2Ca 137-08-6
205-756-7 DL-phenylalanine C9H11NO2 150-30-1
208-407-7 Sodium gluconate C6H12O7.Na 527-07-1
215-665-4 Sorbitan oleate C24H44O6 1338-43-8
231-098-5 Krypton Kr 7439-90-9
231-110-9 Neon Ne 7440-01-9
231-147-0 Argon Ar 7440-37-1
231-168-5 Helium He 7440-59-7
231-172-7 Xenon Xe 7440-63-3
231-783-9 Nitrogen N2 7727-37-9
231-791-2 Water, distilled, conductivity or of similar purity H2O 7732-18-5
232-307-2 Lecithins
The complex combination of diglycerides of fatty acids linked to the choline ester of phosphoric acid 8002-43-5
232-436-4 Syrups, hydrolyzed starch
A complex combination obtained by the hydrolysis of cornstarch by the action of acids or enzymes. It consists primarily of d-glucose, maltose and maltodextrins 8029-43-4
232-442-7 Tallow, hydrogenated 8030-12-4
232-675-4 Dextrin 9004-53-9
232-679-6 Starch
High-polymeric carbohydrate material usually derived from cereal grains such as corn, wheat and sorghum, and from roots and tubers such as potatoes and tapioca. Includes starch which has been pregelatinised by heating in the presence of water 9005-25-8
232-940-4 Maltodextrin 9050-36-6
238-976-7 Sodium D-gluconate C6H12O7.xNa 14906-97-9
248-027-9 D-glucitol monostearate C24H48O7 26836-47-5
262-988-1 Fatty acids, coco, Me esters 61788-59-8
265-995-8 Cellulose pulp 65996-61-4
266-948-4 Glycerides, C16-18 and C18-unsaturated.
This substance is identified by SDA Substance Name: C16-C18 and C18 unsaturated trialkyl glyceride and SDA Reporting Number: 11-001-00 67701-30-8
268-616-4 Syrups, corn, dehydrated 68131-37-3
269-658-6 Glycerides, tallow mono-, di- and tri-, hydrogenated 68308-54-3
270-312-1 Glycerides, C16-18 and C18-unsaturated, mono- and di-
This substance is identified by SDA Substance Name: C16-C18 and C18 unsaturated alkyl and C16-C18 and C18 unsaturated dialkyl glyceride and SDA Reporting Number: 11-002-00 68424-61-3
288-123-8 Glycerides, C10-18 85665-33-4
```

**Shipped sentences**

1. The list of exempted substances has been changed substantially, with a number of entries such as palmitic acid, stearic acid, oleic acid, various vegetable oils, carbon, graphite, vitamin A, and many fatty-acid and glyceride entries present in the earlier list removed from the later one.
2. The later list also adds entries not present before, including fructose, galactose, lactose, and the noble gases krypton, neon, helium and xenon.
3. Some remaining entries have minor wording differences, such as the sorbose entry changing from '1-sorbose' to 'L-sorbose' and small punctuation or capitalisation adjustments in descriptive text for entries like starch, lecithins and the hydrolyzed starch syrup.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 18. `32017R0745@20170505` — `AR 2`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 2
HEADING: Definitions
IN FORCE: not stated
APPLIES FROM: unchanged by this amendment
SUB-PROVISIONS THAT DIFFER: Art. 2(1)(30)
```

**Before**

```
Article 2
Definitions
For the purposes of this Regulation, the following definitions apply:
(1) medical device means any instrument, apparatus, appliance, software, implant, reagent, material or other article intended by the manufacturer to be used, alone or in combination, for human beings for one or more of the following specific medical purposes:
diagnosis, prevention, monitoring, prediction, prognosis, treatment or alleviation of disease,
diagnosis, monitoring, treatment, alleviation of, or compensation for, an injury or disability,
investigation, replacement or modification of the anatomy or of a physiological or pathological process or state,
providing information by means of in vitro examination of specimens derived from the human body, including organ, blood and tissue donations,
and which does not achieve its principal intended action by pharmacological, immunological or metabolic means, in or on the human body, but which may be assisted in its function by such means.
The following products shall also be deemed to be medical devices:
devices for the control or support of conception;
products specifically intended for the cleaning, disinfection or sterilisation of devices as referred to in Article 1(4) and of those referred to in the first paragraph of this point.
(2) accessory for a medical device means an article which, whilst not being itself a medical device, is intended by its manufacturer to be used together with one or several particular medical device(s) to specifically enable the medical device(s) to be used in accordance with its/their intended purpose(s) or to specifically and directly assist the medical functionality of the medical device(s) in terms of its/their intended purpose(s);
(3) custom-made device means any device specifically made in accordance with a written prescription of any person authorised by national law by virtue of that person's professional qualifications which gives, under that person's responsibility, specific design characteristics, and is intended for the sole use of a particular patient exclusively to meet their individual conditions and needs.
However, mass-produced devices which need to be adapted to meet the specific requirements of any professional user and devices which are mass-produced by means of industrial manufacturing processes in accordance with the written prescriptions of any authorised person shall not be considered to be custom-made devices;
(4) active device means any device, the operation of which depends on a source of energy other than that generated by the human body for that purpose, or by gravity, and which acts by changing the density of or converting that energy. Devices intended to transmit energy, substances or other elements between an active device and the patient, without any significant change, shall not be deemed to be active devices.
Software shall also be deemed to be an active device;
(5) implantable device means any device, including those that are partially or wholly absorbed, which is intended:
to be totally introduced into the human body, or
to replace an epithelial surface or the surface of the eye,
by clinical intervention and which is intended to remain in place after the procedure.
Any device intended to be partially introduced into the human body by clinical intervention and intended to remain in place after the procedure for at least 30 days shall also be deemed to be an implantable device;
(6) invasive device means any device which, in whole or in part, penetrates inside the body, either through a body orifice or through the surface of the body;
(7) generic device group means a set of devices having the same or similar intended purposes or a commonality of technology allowing them to be classified in a generic manner not reflecting specific characteristics;
(8) single-use device means a device that is intended to be used on one individual during a single procedure;
(9) falsified device means any device with a false presentation of its identity and/or of its source and/or its CE marking certificates or documents relating to CE marking procedures. This definition does not include unintentional non-compliance and is without prejudice to infringements of intellectual property rights;
(10) procedure pack means a combination of products packaged together and placed on the market with the purpose of being used for a specific medical purpose;
(11) system means a combination of products, either packaged together or not, which are intended to be inter-connected or combined to achieve a specific medical purpose;
(12) intended purpose means the use for which a device is intended according to the data supplied by the manufacturer on the label, in the instructions for use or in promotional or sales materials or statements and as specified by the manufacturer in the clinical evaluation;
(13) label means the written, printed or graphic information appearing either on the device itself, or on the packaging of each unit or on the packaging of multiple devices;
(14) instructions for use means the information provided by the manufacturer to inform the user of a device's intended purpose and proper use and of any precautions to be taken;
(15) Unique Device Identifier (UDI) means a series of numeric or alphanumeric characters that is created through internationally accepted device identification and coding standards and that allows unambiguous identification of specific devices on the market;
(16) non-viable means having no potential for metabolism or multiplication;
(17) derivative means a non-cellular substance extracted from human or animal tissue or cells through a manufacturing process. The final substance used for manufacturing of the device in this case does not contain any cells or tissues;
(18) nanomaterial means a natural, incidental or manufactured material containing particles in an unbound state or as an aggregate or as an agglomerate and where, for 50 % or more of the particles in the number size distribution, one or more external dimensions is in the size range 1-100 nm;
Fullerenes, graphene flakes and single-wall carbon nanotubes with one or more external dimensions below 1 nm shall also be deemed to be nanomaterials;
(19) particle, for the purposes of the definition of nanomaterial in point (18), means a minute piece of matter with defined physical boundaries;
(20) agglomerate, for the purposes of the definition of nanomaterial in point (18), means a collection of weakly bound particles or aggregates where the resulting external surface area is similar to the sum of the surface areas of the individual components;
(21) aggregate, for the purposes of the definition of nanomaterial in point (18), means a particle comprising of strongly bound or fused particles;
(22) performance means the ability of a device to achieve its intended purpose as stated by the manufacturer;
(23) risk means the combination of the probability of occurrence of harm and the severity of that harm;
(24) benefit-risk determination means the analysis of all assessments of benefit and risk of possible relevance for the use of the device for the intended purpose, when used in accordance with the intended purpose given by the manufacturer;
(25) compatibility is the ability of a device, including software, when used together with one or more other devices in accordance with its intended purpose, to:
(a) perform without losing or compromising the ability to perform as intended, and/or
(b) integrate and/or operate without the need for modification or adaption of any part of the combined devices, and/or
(c) be used together without conflict/interference or adverse reaction.
(26) interoperability is the ability of two or more devices, including software, from the same manufacturer or from different manufacturers, to:
(a) exchange information and use the information that has been exchanged for the correct execution of a specified function without changing the content of the data, and/or
(b) communicate with each other, and/or
(c) work together as intended.
(27) making available on the market means any supply of a device, other than an investigational device, for distribution, consumption or use on the Union market in the course of a commercial activity, whether in return for payment or free of charge;
(28) placing on the market means the first making available of a device, other than an investigational device, on the Union market;
(29) putting into service means the stage at which a device, other than an investigational device, has been made available to the final user as being ready for use on the Union market for the first time for its intended purpose;
(30) manufacturer means a natural or legal person who manufactures or fully refurbishes a device or has a device designed, manufactured or fully refurbished, and markets that device under its name or trademark;
(31) fully refurbishing, for the purposes of the definition of manufacturer, means the complete rebuilding of a device already placed on the market or put into service, or the making of a new device from used devices, to bring it into conformity with this Regulation, combined with the assignment of a new lifetime to the refurbished device;
(32) authorised representative means any natural or legal person established within the Union who has received and accepted a written mandate from a manufacturer, located outside the Union, to act on the manufacturer's behalf in relation to specified tasks with regard to the latter's obligations under this Regulation;
(33) importer means any natural or legal person established within the Union that places a device from a third country on the Union market;
(34) distributor means any natural or legal person in the supply chain, other than the manufacturer or the importer, that makes a device available on the market, up until the point of putting into service;
(35) economic operator means a manufacturer, an authorised representative, an importer, a distributor or the person referred to in Article 22(1) and 22(3);
(36) health institution means an organisation the primary purpose of which is the care or treatment of patients or the promotion of public health;
(37) user means any healthcare professional or lay person who uses a device;
(38) lay person means an individual who does not have formal education in a relevant field of healthcare or medical discipline;
(39) reprocessing means a process carried out on a used device in order to allow its safe reuse including cleaning, disinfection, sterilisation and related procedures, as well as testing and restoring the technical and functional safety of the used device;
(40) conformity assessment means the process demonstrating whether the requirements of this Regulation relating to a device have been fulfilled;
(41) conformity assessment body means a body that performs third-party conformity assessment activities including calibration, testing, certification and inspection;
(42) notified body means a conformity assessment body designated in accordance with this Regulation;
(43) CE marking of conformity or CE marking means a marking by which a manufacturer indicates that a device is in conformity with the applicable requirements set out in this Regulation and other applicable Union harmonisation legislation providing for its affixing;
(44) clinical evaluation means a systematic and planned process to continuously generate, collect, analyse and assess the clinical data pertaining to a device in order to verify the safety and performance, including clinical benefits, of the device when used as intended by the manufacturer;
(45) clinical investigation means any systematic investigation involving one or more human subjects, undertaken to assess the safety or performance of a device;
(46) investigational device means a device that is assessed in a clinical investigation;
(47) clinical investigation plan means a document that describes the rationale, objectives, design, methodology, monitoring, statistical considerations, organisation and conduct of a clinical investigation;
(48) clinical data means information concerning safety or performance that is generated from the use of a device and is sourced from the following:
clinical investigation(s) of the device concerned,
clinical investigation(s) or other studies reported in scientific literature, of a device for which equivalence to the device in question can be demonstrated,
reports published in peer reviewed scientific literature on other clinical experience of either the device in question or a device for which equivalence to the device in question can be demonstrated,
clinically relevant information coming from post-market surveillance, in particular the post-market clinical follow-up;
(49) sponsor means any individual, company, institution or organisation which takes responsibility for the initiation, for the management and setting up of the financing of the clinical investigation;
(50) subject means an individual who participates in a clinical investigation;
(51) clinical evidence means clinical data and clinical evaluation results pertaining to a device of a sufficient amount and quality to allow a qualified assessment of whether the device is safe and achieves the intended clinical benefit(s), when used as intended by the manufacturer;
(52) clinical performance means the ability of a device, resulting from any direct or indirect medical effects which stem from its technical or functional characteristics, including diagnostic characteristics, to achieve its intended purpose as claimed by the manufacturer, thereby leading to a clinical benefit for patients, when used as intended by the manufacturer;
(53) clinical benefit means the positive impact of a device on the health of an individual, expressed in terms of a meaningful, measurable, patient-relevant clinical outcome(s), including outcome(s) related to diagnosis, or a positive impact on patient management or public health;
(54) investigator means an individual responsible for the conduct of a clinical investigation at a clinical investigation site;
(55) informed consent means a subject's free and voluntary expression of his or her willingness to participate in a particular clinical investigation, after having been informed of all aspects of the clinical investigation that are relevant to the subject's decision to participate or, in the case of minors and of incapacitated subjects, an authorisation or agreement from their legally designated representative to include them in the clinical investigation;
(56) ethics committee means an independent body established in a Member State in accordance with the law of that Member State and empowered to give opinions for the purposes of this Regulation, taking into account the views of laypersons, in particular patients or patients' organisations;
(57) adverse event means any untoward medical occurrence, unintended disease or injury or any untoward clinical signs, including an abnormal laboratory finding, in subjects, users or other persons, in the context of a clinical investigation, whether or not related to the investigational device;
(58) serious adverse event means any adverse event that led to any of the following:
(a) death,
(b) serious deterioration in the health of the subject, that resulted in any of the following:
(i) life-threatening illness or injury,
(ii) permanent impairment of a body structure or a body function,
(iii) hospitalisation or prolongation of patient hospitalisation,
(iv) medical or surgical intervention to prevent life-threatening illness or injury or permanent impairment to a body structure or a body function,
(v) chronic disease,
(c) foetal distress, foetal death or a congenital physical or mental impairment or birth defect;
(59) device deficiency means any inadequacy in the identity, quality, durability, reliability, safety or performance of an investigational device, including malfunction, use errors or inadequacy in information supplied by the manufacturer;
(60) post-market surveillance means all activities carried out by manufacturers in cooperation with other economic operators to institute and keep up to date a systematic procedure to proactively collect and review experience gained from devices they place on the market, make available on the market or put into service for the purpose of identifying any need to immediately apply any necessary corrective or preventive actions;
(61) market surveillance means the activities carried out and measures taken by competent authorities to check and ensure that devices comply with the requirements set out in the relevant Union harmonisation legislation and do not endanger health, safety or any other aspect of public interest protection;
(62) recall means any measure aimed at achieving the return of a device that has already been made available to the end user;
(63) withdrawal means any measure aimed at preventing a device in the supply chain from being further made available on the market;
(64) incident means any malfunction or deterioration in the characteristics or performance of a device made available on the market, including use-error due to ergonomic features, as well as any inadequacy in the information supplied by the manufacturer and any undesirable side-effect;
(65) serious incident means any incident that directly or indirectly led, might have led or might lead to any of the following:
(a) the death of a patient, user or other person,
(b) the temporary or permanent serious deterioration of a patient's, user's or other person's state of health,
(c) a serious public health threat;
(66) serious public health threat means an event which could result in imminent risk of death, serious deterioration in a person's state of health, or serious illness, that may require prompt remedial action, and that may cause significant morbidity or mortality in humans, or that is unusual or unexpected for the given place and time;
(67) corrective action means action taken to eliminate the cause of a potential or actual non-conformity or other undesirable situation;
(68) field safety corrective action means corrective action taken by a manufacturer for technical or medical reasons to prevent or reduce the risk of a serious incident in relation to a device made available on the market;
(69) field safety notice means a communication sent by a manufacturer to users or customers in relation to a field safety corrective action;
(70) harmonised standard means a European standard as defined in point (1)(c) of Article 2 of Regulation (EU) No 1025/2012;
(71) common specifications (CS) means a set of technical and/or clinical requirements, other than a standard, that provides a means of complying with the legal obligations applicable to a device, process or system.
```

**After**

```
Article 2
Definitions
For the purposes of this Regulation, the following definitions apply:
(1) medical device means any instrument, apparatus, appliance, software, implant, reagent, material or other article intended by the manufacturer to be used, alone or in combination, for human beings for one or more of the following specific medical purposes:
diagnosis, prevention, monitoring, prediction, prognosis, treatment or alleviation of disease,
diagnosis, monitoring, treatment, alleviation of, or compensation for, an injury or disability,
investigation, replacement or modification of the anatomy or of a physiological or pathological process or state,
providing information by means of in vitro examination of specimens derived from the human body, including organ, blood and tissue donations,
and which does not achieve its principal intended action by pharmacological, immunological or metabolic means, in or on the human body, but which may be assisted in its function by such means.
The following products shall also be deemed to be medical devices:
devices for the control or support of conception;
products specifically intended for the cleaning, disinfection or sterilisation of devices as referred to in Article 1(4) and of those referred to in the first paragraph of this point.
(2) accessory for a medical device means an article which, whilst not being itself a medical device, is intended by its manufacturer to be used together with one or several particular medical device(s) to specifically enable the medical device(s) to be used in accordance with its/their intended purpose(s) or to specifically and directly assist the medical functionality of the medical device(s) in terms of its/their intended purpose(s);
(3) custom-made device means any device specifically made in accordance with a written prescription of any person authorised by national law by virtue of that person's professional qualifications which gives, under that person's responsibility, specific design characteristics, and is intended for the sole use of a particular patient exclusively to meet their individual conditions and needs.
However, mass-produced devices which need to be adapted to meet the specific requirements of any professional user and devices which are mass-produced by means of industrial manufacturing processes in accordance with the written prescriptions of any authorised person shall not be considered to be custom-made devices;
(4) active device means any device, the operation of which depends on a source of energy other than that generated by the human body for that purpose, or by gravity, and which acts by changing the density of or converting that energy. Devices intended to transmit energy, substances or other elements between an active device and the patient, without any significant change, shall not be deemed to be active devices.
Software shall also be deemed to be an active device;
(5) implantable device means any device, including those that are partially or wholly absorbed, which is intended:
to be totally introduced into the human body, or
to replace an epithelial surface or the surface of the eye,
by clinical intervention and which is intended to remain in place after the procedure.
Any device intended to be partially introduced into the human body by clinical intervention and intended to remain in place after the procedure for at least 30 days shall also be deemed to be an implantable device;
(6) invasive device means any device which, in whole or in part, penetrates inside the body, either through a body orifice or through the surface of the body;
(7) generic device group means a set of devices having the same or similar intended purposes or a commonality of technology allowing them to be classified in a generic manner not reflecting specific characteristics;
(8) single-use device means a device that is intended to be used on one individual during a single procedure;
(9) falsified device means any device with a false presentation of its identity and/or of its source and/or its CE marking certificates or documents relating to CE marking procedures. This definition does not include unintentional non-compliance and is without prejudice to infringements of intellectual property rights;
(10) procedure pack means a combination of products packaged together and placed on the market with the purpose of being used for a specific medical purpose;
(11) system means a combination of products, either packaged together or not, which are intended to be inter-connected or combined to achieve a specific medical purpose;
(12) intended purpose means the use for which a device is intended according to the data supplied by the manufacturer on the label, in the instructions for use or in promotional or sales materials or statements and as specified by the manufacturer in the clinical evaluation;
(13) label means the written, printed or graphic information appearing either on the device itself, or on the packaging of each unit or on the packaging of multiple devices;
(14) instructions for use means the information provided by the manufacturer to inform the user of a device's intended purpose and proper use and of any precautions to be taken;
(15) Unique Device Identifier (UDI) means a series of numeric or alphanumeric characters that is created through internationally accepted device identification and coding standards and that allows unambiguous identification of specific devices on the market;
(16) non-viable means having no potential for metabolism or multiplication;
(17) derivative means a non-cellular substance extracted from human or animal tissue or cells through a manufacturing process. The final substance used for manufacturing of the device in this case does not contain any cells or tissues;
(18) nanomaterial means a natural, incidental or manufactured material containing particles in an unbound state or as an aggregate or as an agglomerate and where, for 50 % or more of the particles in the number size distribution, one or more external dimensions is in the size range 1-100 nm;
Fullerenes, graphene flakes and single-wall carbon nanotubes with one or more external dimensions below 1 nm shall also be deemed to be nanomaterials;
(19) particle, for the purposes of the definition of nanomaterial in point (18), means a minute piece of matter with defined physical boundaries;
(20) agglomerate, for the purposes of the definition of nanomaterial in point (18), means a collection of weakly bound particles or aggregates where the resulting external surface area is similar to the sum of the surface areas of the individual components;
(21) aggregate, for the purposes of the definition of nanomaterial in point (18), means a particle comprising of strongly bound or fused particles;
(22) performance means the ability of a device to achieve its intended purpose as stated by the manufacturer;
(23) risk means the combination of the probability of occurrence of harm and the severity of that harm;
(24) benefit-risk determination means the analysis of all assessments of benefit and risk of possible relevance for the use of the device for the intended purpose, when used in accordance with the intended purpose given by the manufacturer;
(25) compatibility is the ability of a device, including software, when used together with one or more other devices in accordance with its intended purpose, to:
(a) perform without losing or compromising the ability to perform as intended, and/or
(b) integrate and/or operate without the need for modification or adaption of any part of the combined devices, and/or
(c) be used together without conflict/interference or adverse reaction.
(26) interoperability is the ability of two or more devices, including software, from the same manufacturer or from different manufacturers, to:
(a) exchange information and use the information that has been exchanged for the correct execution of a specified function without changing the content of the data, and/or
(b) communicate with each other, and/or
(c) work together as intended.
(27) making available on the market means any supply of a device, other than an investigational device, for distribution, consumption or use on the Union market in the course of a commercial activity, whether in return for payment or free of charge;
(28) placing on the market means the first making available of a device, other than an investigational device, on the Union market;
(29) putting into service means the stage at which a device, other than an investigational device, has been made available to the final user as being ready for use on the Union market for the first time for its intended purpose;
(30) manufacturer means a natural or legal person who manufactures or fully refurbishes a device or has a device designed, manufactured or fully refurbished, and markets that device under its name or trade mark;
(31) fully refurbishing, for the purposes of the definition of manufacturer, means the complete rebuilding of a device already placed on the market or put into service, or the making of a new device from used devices, to bring it into conformity with this Regulation, combined with the assignment of a new lifetime to the refurbished device;
(32) authorised representative means any natural or legal person established within the Union who has received and accepted a written mandate from a manufacturer, located outside the Union, to act on the manufacturer's behalf in relation to specified tasks with regard to the latter's obligations under this Regulation;
(33) importer means any natural or legal person established within the Union that places a device from a third country on the Union market;
(34) distributor means any natural or legal person in the supply chain, other than the manufacturer or the importer, that makes a device available on the market, up until the point of putting into service;
(35) economic operator means a manufacturer, an authorised representative, an importer, a distributor or the person referred to in Article 22(1) and 22(3);
(36) health institution means an organisation the primary purpose of which is the care or treatment of patients or the promotion of public health;
(37) user means any healthcare professional or lay person who uses a device;
(38) lay person means an individual who does not have formal education in a relevant field of healthcare or medical discipline;
(39) reprocessing means a process carried out on a used device in order to allow its safe reuse including cleaning, disinfection, sterilisation and related procedures, as well as testing and restoring the technical and functional safety of the used device;
(40) conformity assessment means the process demonstrating whether the requirements of this Regulation relating to a device have been fulfilled;
(41) conformity assessment body means a body that performs third-party conformity assessment activities including calibration, testing, certification and inspection;
(42) notified body means a conformity assessment body designated in accordance with this Regulation;
(43) CE marking of conformity or CE marking means a marking by which a manufacturer indicates that a device is in conformity with the applicable requirements set out in this Regulation and other applicable Union harmonisation legislation providing for its affixing;
(44) clinical evaluation means a systematic and planned process to continuously generate, collect, analyse and assess the clinical data pertaining to a device in order to verify the safety and performance, including clinical benefits, of the device when used as intended by the manufacturer;
(45) clinical investigation means any systematic investigation involving one or more human subjects, undertaken to assess the safety or performance of a device;
(46) investigational device means a device that is assessed in a clinical investigation;
(47) clinical investigation plan means a document that describes the rationale, objectives, design, methodology, monitoring, statistical considerations, organisation and conduct of a clinical investigation;
(48) clinical data means information concerning safety or performance that is generated from the use of a device and is sourced from the following:
clinical investigation(s) of the device concerned,
clinical investigation(s) or other studies reported in scientific literature, of a device for which equivalence to the device in question can be demonstrated,
reports published in peer reviewed scientific literature on other clinical experience of either the device in question or a device for which equivalence to the device in question can be demonstrated,
clinically relevant information coming from post-market surveillance, in particular the post-market clinical follow-up;
(49) sponsor means any individual, company, institution or organisation which takes responsibility for the initiation, for the management and setting up of the financing of the clinical investigation;
(50) subject means an individual who participates in a clinical investigation;
(51) clinical evidence means clinical data and clinical evaluation results pertaining to a device of a sufficient amount and quality to allow a qualified assessment of whether the device is safe and achieves the intended clinical benefit(s), when used as intended by the manufacturer;
(52) clinical performance means the ability of a device, resulting from any direct or indirect medical effects which stem from its technical or functional characteristics, including diagnostic characteristics, to achieve its intended purpose as claimed by the manufacturer, thereby leading to a clinical benefit for patients, when used as intended by the manufacturer;
(53) clinical benefit means the positive impact of a device on the health of an individual, expressed in terms of a meaningful, measurable, patient-relevant clinical outcome(s), including outcome(s) related to diagnosis, or a positive impact on patient management or public health;
(54) investigator means an individual responsible for the conduct of a clinical investigation at a clinical investigation site;
(55) informed consent means a subject's free and voluntary expression of his or her willingness to participate in a particular clinical investigation, after having been informed of all aspects of the clinical investigation that are relevant to the subject's decision to participate or, in the case of minors and of incapacitated subjects, an authorisation or agreement from their legally designated representative to include them in the clinical investigation;
(56) ethics committee means an independent body established in a Member State in accordance with the law of that Member State and empowered to give opinions for the purposes of this Regulation, taking into account the views of laypersons, in particular patients or patients' organisations;
(57) adverse event means any untoward medical occurrence, unintended disease or injury or any untoward clinical signs, including an abnormal laboratory finding, in subjects, users or other persons, in the context of a clinical investigation, whether or not related to the investigational device;
(58) serious adverse event means any adverse event that led to any of the following:
(a) death,
(b) serious deterioration in the health of the subject, that resulted in any of the following:
(i) life-threatening illness or injury,
(ii) permanent impairment of a body structure or a body function,
(iii) hospitalisation or prolongation of patient hospitalisation,
(iv) medical or surgical intervention to prevent life-threatening illness or injury or permanent impairment to a body structure or a body function,
(v) chronic disease,
(c) foetal distress, foetal death or a congenital physical or mental impairment or birth defect;
(59) device deficiency means any inadequacy in the identity, quality, durability, reliability, safety or performance of an investigational device, including malfunction, use errors or inadequacy in information supplied by the manufacturer;
(60) post-market surveillance means all activities carried out by manufacturers in cooperation with other economic operators to institute and keep up to date a systematic procedure to proactively collect and review experience gained from devices they place on the market, make available on the market or put into service for the purpose of identifying any need to immediately apply any necessary corrective or preventive actions;
(61) market surveillance means the activities carried out and measures taken by competent authorities to check and ensure that devices comply with the requirements set out in the relevant Union harmonisation legislation and do not endanger health, safety or any other aspect of public interest protection;
(62) recall means any measure aimed at achieving the return of a device that has already been made available to the end user;
(63) withdrawal means any measure aimed at preventing a device in the supply chain from being further made available on the market;
(64) incident means any malfunction or deterioration in the characteristics or performance of a device made available on the market, including use-error due to ergonomic features, as well as any inadequacy in the information supplied by the manufacturer and any undesirable side-effect;
(65) serious incident means any incident that directly or indirectly led, might have led or might lead to any of the following:
(a) the death of a patient, user or other person,
(b) the temporary or permanent serious deterioration of a patient's, user's or other person's state of health,
(c) a serious public health threat;
(66) serious public health threat means an event which could result in imminent risk of death, serious deterioration in a person's state of health, or serious illness, that may require prompt remedial action, and that may cause significant morbidity or mortality in humans, or that is unusual or unexpected for the given place and time;
(67) corrective action means action taken to eliminate the cause of a potential or actual non-conformity or other undesirable situation;
(68) field safety corrective action means corrective action taken by a manufacturer for technical or medical reasons to prevent or reduce the risk of a serious incident in relation to a device made available on the market;
(69) field safety notice means a communication sent by a manufacturer to users or customers in relation to a field safety corrective action;
(70) harmonised standard means a European standard as defined in point (1)(c) of Article 2 of Regulation (EU) No 1025/2012;
(71) common specifications (CS) means a set of technical and/or clinical requirements, other than a standard, that provides a means of complying with the legal obligations applicable to a device, process or system.
```

**Shipped sentences**

1. In the definition of manufacturer, the phrase describing marketing of a device under the person's name has been changed from a one-word spelling to a two-word spelling of trademark.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 19. `32017R0745@20200424` — `AR 59`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Art. 59
HEADING: Derogation from the conformity assessment procedures
IN FORCE: 2020-04-24
APPLIES FROM: unknown (the text changed beyond its dates, so no date that moved can be read as the application date)
DATES ADDED: 2020-04-24, 2021-05-25
SUB-PROVISIONS THAT DIFFER: Art. 59(1)(1), Art. 59(2)(2), Art. 59(3)(1)
```

**Before**

```
Article 59
Derogation from the conformity assessment procedures
1. By way of derogation from Article 52, any competent authority may authorise, on a duly justified request, the placing on the market or putting into service within the territory of the Member State concerned, of a specific device for which the procedures referred to in that Article have not been carried out but use of which is in the interest of public health or patient safety or health.
2. The Member State shall inform the Commission and the other Member States of any decision to authorise the placing on the market or putting into service of a device in accordance with paragraph 1 where such authorisation is granted for use other than for a single patient.
3. Following a notification pursuant to paragraph 2 of this Article, the Commission, in exceptional cases relating to public health or patient safety or health, may, by means of implementing acts, extend for a limited period of time the validity of an authorisation granted by a Member State in accordance with paragraph 1 of this Article to the territory of the Union and set the conditions under which the device may be placed on the market or put into service. Those implementing acts shall be adopted in accordance with the examination procedure referred to in Article 114(3).
On duly justified imperative grounds of urgency relating to the health and safety of humans, the Commission shall adopt immediately applicable implementing acts in accordance with the procedure referred to in Article 114(4).
```

**After**

```
Article 59
Derogation from the conformity assessment procedures
1. By way of derogation from Article 52 of this Regulation or, for the period from 24 April 2020 to 25 May 2021, by way of derogation from Article 9(1) and (2) of Directive 90/385/EEC or from Article 11(1) to (6) of Directive 93/42/EEC, any competent authority may authorise, on a duly justified request, the placing on the market or putting into service within the territory of the Member State concerned, of a specific device for which the applicable procedures referred to in those Articles have not been carried out but use of which is in the interest of public health or patient safety or health.
2. The Member State shall inform the Commission and the other Member States of any decision to authorise the placing on the market or putting into service of a device in accordance with paragraph 1 where such authorisation is granted for use other than for a single patient.
The Member State may inform the Commission and the other Member States of any authorisation granted in accordance with Article 9(9) of Directive 90/385/EEC or Article 11(13) of Directive 93/42/EEC before 24 April 2020.
3. Following a notification pursuant to paragraph 2 of this Article, the Commission, in exceptional cases relating to public health or patient safety or health, may, by means of implementing acts, extend for a limited period of time the validity of an authorisation granted by a Member State in accordance with paragraph 1 of this Article or, when granted before 24 April 2020, in accordance with Article 9(9) of Directive 90/385/EEC or Article 11(13) of Directive 93/42/EEC to the territory of the Union and set the conditions under which the device may be placed on the market or put into service. Those implementing acts shall be adopted in accordance with the examination procedure referred to in Article 114(3).
On duly justified imperative grounds of urgency relating to the health and safety of humans, the Commission shall adopt immediately applicable implementing acts in accordance with the procedure referred to in Article 114(4).
```

**Shipped sentences**

1. Paragraph 1 now adds that, for the period from 24 April 2020 to 25 May 2021, the derogation may also apply by way of derogation from Article 9(1) and (2) of Directive 90/385/EEC or Article 11(1) to (6) of Directive 93/42/EEC, alongside Article 52 of the Regulation, and refers to procedures under "those Articles" rather than only "that Article".
2. Paragraph 2 gains a new sentence allowing the Member State to inform the Commission and other Member States of authorisations granted under Article 9(9) of Directive 90/385/EEC or Article 11(13) of Directive 93/42/EEC before 24 April 2020, in addition to the existing notification duty.
3. Paragraph 3 correspondingly extends the Commission's power to extend the validity of authorisations to cover those granted before 24 April 2020 under Article 9(9) of Directive 90/385/EEC or Article 11(13) of Directive 93/42/EEC, in addition to authorisations granted under paragraph 1.

- [ ] Faithful
- [ ] Not faithful — reason: 

## 20. `32017R0745@20260101` — `AN I`

- Change type: `MODIFIED` · gate outcome: `passed`
- LLM judge: `faithful=true`

**PIPELINE HEADER (established by the deterministic pipeline, not a text)**

```
CHANGE TYPE (established by a structural diff, not by you): MODIFIED — this provision exists in both versions and its text differs.
PROVISION: Annex I
HEADING: ANNEX I
IN FORCE: 2026-01-01
APPLIES FROM: unknown (the text changed beyond its dates, so no date that moved can be read as the application date)
DATES REMOVED: 2018-05-26, 2020-05-26
SUB-PROVISIONS THAT DIFFER: Annex I section 10 section 10.4 section 10.4.1(b), Annex I section 10 section 10.4 section 10.4.2(d), Annex I section 10 section 10.4 section 10.4.3, Annex I section 10 section 10.4 section 10.4.4
```

**Before**

```
ANNEX I
GENERAL SAFETY AND PERFORMANCE REQUIREMENTS
CHAPTER I
GENERAL REQUIREMENTS
1. Devices shall achieve the performance intended by their manufacturer and shall be designed and manufactured in such a way that, during normal conditions of use, they are suitable for their intended purpose. They shall be safe and effective and shall not compromise the clinical condition or the safety of patients, or the safety and health of users or, where applicable, other persons, provided that any risks which may be associated with their use constitute acceptable risks when weighed against the benefits to the patient and are compatible with a high level of protection of health and safety, taking into account the generally acknowledged state of the art.
2. The requirement in this Annex to reduce risks as far as possible means the reduction of risks as far as possible without adversely affecting the benefit-risk ratio.
3. Manufacturers shall establish, implement, document and maintain a risk management system.
Risk management shall be understood as a continuous iterative process throughout the entire lifecycle of a device, requiring regular systematic updating. In carrying out risk management manufacturers shall:
(a) establish and document a risk management plan for each device;
(b) identify and analyse the known and foreseeable hazards associated with each device;
(c) estimate and evaluate the risks associated with, and occurring during, the intended use and during reasonably foreseeable misuse;
(d) eliminate or control the risks referred to in point (c) in accordance with the requirements of Section 4;
(e) evaluate the impact of information from the production phase and, in particular, from the post-market surveillance system, on hazards and the frequency of occurrence thereof, on estimates of their associated risks, as well as on the overall risk, benefit-risk ratio and risk acceptability; and
(f) based on the evaluation of the impact of the information referred to in point (e), if necessary amend control measures in line with the requirements of Section 4.
4. Risk control measures adopted by manufacturers for the design and manufacture of the devices shall conform to safety principles, taking account of the generally acknowledged state of the art. To reduce risks, Manufacturers shall manage risks so that the residual risk associated with each hazard as well as the overall residual risk is judged acceptable. In selecting the most appropriate solutions, manufacturers shall, in the following order of priority:
(a) eliminate or reduce risks as far as possible through safe design and manufacture;
(b) where appropriate, take adequate protection measures, including alarms if necessary, in relation to risks that cannot be eliminated; and
(c) provide information for safety (warnings/precautions/contra-indications) and, where appropriate, training to users.
Manufacturers shall inform users of any residual risks.
5. In eliminating or reducing risks related to use error, the manufacturer shall:
(a) reduce as far as possible the risks related to the ergonomic features of the device and the environment in which the device is intended to be used (design for patient safety), and
(b) give consideration to the technical knowledge, experience, education, training and use environment, where applicable, and the medical and physical conditions of intended users (design for lay, professional, disabled or other users).
6. The characteristics and performance of a device shall not be adversely affected to such a degree that the health or safety of the patient or the user and, where applicable, of other persons are compromised during the lifetime of the device, as indicated by the manufacturer, when the device is subjected to the stresses which can occur during normal conditions of use and has been properly maintained in accordance with the manufacturer's instructions.
7. Devices shall be designed, manufactured and packaged in such a way that their characteristics and performance during their intended use are not adversely affected during transport and storage, for example, through fluctuations of temperature and humidity, taking account of the instructions and information provided by the manufacturer.
8. All known and foreseeable risks, and any undesirable side-effects, shall be minimised and be acceptable when weighed against the evaluated benefits to the patient and/or user arising from the achieved performance of the device during normal conditions of use.
9. For the devices referred to in Annex XVI, the general safety requirements set out in Sections 1 and 8 shall be understood to mean that the device, when used under the conditions and for the purposes intended, does not present a risk at all or presents a risk that is no more than the maximum acceptable risk related to the product's use which is consistent with a high level of protection for the safety and health of persons.
CHAPTER II
REQUIREMENTS REGARDING DESIGN AND MANUFACTURE
10. Chemical, physical and biological properties
10.1. Devices shall be designed and manufactured in such a way as to ensure that the characteristics and performance requirements referred to in Chapter I are fulfilled. Particular attention shall be paid to:
(a) the choice of materials and substances used, particularly as regards toxicity and, where relevant, flammability;
(b) the compatibility between the materials and substances used and biological tissues, cells and body fluids, taking account of the intended purpose of the device and, where relevant, absorption, distribution, metabolism and excretion;
(c) the compatibility between the different parts of a device which consists of more than one implantable part;
(d) the impact of processes on material properties;
(e) where appropriate, the results of biophysical or modelling research the validity of which has been demonstrated beforehand;
(f) the mechanical properties of the materials used, reflecting, where appropriate, matters such as strength, ductility, fracture resistance, wear resistance and fatigue resistance;
(g) surface properties; and
(h) the confirmation that the device meets any defined chemical and/or physical specifications.
10.2. Devices shall be designed, manufactured and packaged in such a way as to minimise the risk posed by contaminants and residues to patients, taking account of the intended purpose of the device, and to the persons involved in the transport, storage and use of the devices. Particular attention shall be paid to tissues exposed to those contaminants and residues and to the duration and frequency of exposure.
10.3. Devices shall be designed and manufactured in such a way that they can be used safely with the materials and substances, including gases, with which they enter into contact during their intended use; if the devices are intended to administer medicinal products they shall be designed and manufactured in such a way as to be compatible with the medicinal products concerned in accordance with the provisions and restrictions governing those medicinal products and that the performance of both the medicinal products and of the devices is maintained in accordance with their respective indications and intended use.
10.4. Substances
10.4.1. Design and manufacture of devices
Devices shall be designed and manufactured in such a way as to reduce as far as possible the risks posed by substances or particles, including wear debris, degradation products and processing residues, that may be released from the device.
Devices, or those parts thereof or those materials used therein that:
are invasive and come into direct contact with the human body,
(re)administer medicines, body liquids or other substances, including gases, to/from the body, or
transport or store such medicines, body fluids or substances, including gases, to be (re)administered to the body,
shall only contain the following substances in a concentration that is above 0,1 % weight by weight (w/w) where justified pursuant to Section 10.4.2:
(a) substances which are carcinogenic, mutagenic or toxic to reproduction (CMR), of category 1A or 1B, in accordance with Part 3 of Annex VI to Regulation (EC) No 1272/2008 of the European Parliament and of the CouncilRegulation (EC) No 1272/2008 of the European Parliament and of the Council of 16 December 2008 on classification, labelling and packaging of substances and mixtures, amending and repealing Directives 67/548/EEC and 1999/45/EC, and amending Regulation (EC) No 1907/2006 ( OJ L 353, 31.12.2008, p. 1)., or
(b) substances having endocrine-disrupting properties for which there is scientific evidence of probable serious effects to human health and which are identified either in accordance with the procedure set out in Article 59 of Regulation (EC) No 1907/2006 of the European Parliament and of the CouncilRegulation (EC) No 1907/2006 of the European Parliament and of the Council of 18 December 2006 concerning the Registration, Evaluation, Authorisation and Restriction of Chemicals (REACH) (OJ L 396, 30.12.2006, p. 1). or, once a delegated act has been adopted by the Commission pursuant to the first subparagraph of Article 5(3) of Regulation (EU) No 528/2012 of the European Parliament and the CouncilRegulation (EU) No 528/2012 of the European Parliament and the Council of 22 May 2012 concerning the making available on the market of and use of biocidal products (OJ L 167, 27.6.2012, p. 1)., in accordance with the criteria that are relevant to human health amongst the criteria established therein.
10.4.2. Justification regarding the presence of CMR and/or endocrine-disrupting substances
The justification for the presence of such substances shall be based upon:
(a) an analysis and estimation of potential patient or user exposure to the substance;
(b) an analysis of possible alternative substances, materials or designs, including, where available, information about independent research, peer-reviewed studies, scientific opinions from relevant scientific committees and an analysis of the availability of such alternatives;
(c) argumentation as to why possible substance and/ or material substitutes, if available, or design changes, if feasible, are inappropriate in relation to maintaining the functionality, performance and the benefit-risk ratios of the product; including taking into account if the intended use of such devices includes treatment of children or treatment of pregnant or breastfeeding women or treatment of other patient groups considered particularly vulnerable to such substances and/or materials; and
(d) where applicable and available, the latest relevant scientific committee guidelines in accordance with Sections 10.4.3. and 10.4.4.
10.4.3. Guidelines on phthalates
For the purposes of Section 10.4., the Commission shall, as soon as possible and by 26 May 2018, provide the relevant scientific committee with a mandate to prepare guidelines that shall be ready before 26 May 2020. The mandate for the committee shall encompass at least a benefit-risk assessment of the presence of phthalates which belong to either of the groups of substances referred to in points (a) and (b) of Section 10.4.1. The benefit-risk assessment shall take into account the intended purpose and context of the use of the device, as well as any available alternative substances and alternative materials, designs or medical treatments. When deemed appropriate on the basis of the latest scientific evidence, but at least every five years, the guidelines shall be updated.
10.4.4. Guidelines on other CMR and endocrine-disrupting substances
Subsequently, the Commission shall mandate the relevant scientific committee to prepare guidelines as referred to in Section 10.4.3. also for other substances referred to in points (a) and (b) of Section 10.4.1., where appropriate.
10.4.5. Labelling
Where devices, parts thereof or materials used therein as referred to in Section 10.4.1. contain substances referred to in points (a) or (b) of Section 10.4.1. in a concentration above 0,1 % weight by weight (w/w), the presence of those substances shall be labelled on the device itself and/or on the packaging for each unit or, where appropriate, on the sales packaging, with the list of such substances. If the intended use of such devices includes treatment of children or treatment of pregnant or breastfeeding women or treatment of other patient groups considered particularly vulnerable to such substances and/or materials, information on residual risks for those patient groups and, if applicable, on appropriate precautionary measures shall be given in the instructions for use.
10.5. Devices shall be designed and manufactured in such a way as to reduce as far as possible the risks posed by the unintentional ingress of substances into the device taking into account the device and the nature of the environment in which it is intended to be used.
10.6. Devices shall be designed and manufactured in such a way as to reduce as far as possible the risks linked to the size and the properties of particles which are or can be released into the patient's or user's body, unless they come into contact with intact skin only. Special attention shall be given to nanomaterials.
11. Infection and microbial contamination
11.1. Devices and their manufacturing processes shall be designed in such a way as to eliminate or to reduce as far as possible the risk of infection to patients, users and, where applicable, other persons. The design shall:
(a) reduce as far as possible and appropriate the risks from unintended cuts and pricks, such as needle stick injuries,
(b) allow easy and safe handling,
(c) reduce as far as possible any microbial leakage from the device and/or microbial exposure during use, and
(d) prevent microbial contamination of the device or its content such as specimens or fluids.
11.2. Where necessary devices shall be designed to facilitate their safe cleaning, disinfection, and/or re-sterilisation.
11.3. Devices labelled as having a specific microbial state shall be designed, manufactured and packaged to ensure that they remain in that state when placed on the market and remain so under the transport and storage conditions specified by the manufacturer.
11.4. Devices delivered in a sterile state shall be designed, manufactured and packaged in accordance with appropriate procedures, to ensure that they are sterile when placed on the market and that, unless the packaging which is intended to maintain their sterile condition is damaged, they remain sterile, under the transport and storage conditions specified by the manufacturer, until that packaging is opened at the point of use. It shall be ensured that the integrity of that packaging is clearly evident to the final user.
11.5. Devices labelled as sterile shall be processed, manufactured, packaged and, sterilised by means of appropriate, validated methods.
11.6. Devices intended to be sterilised shall be manufactured and packaged in appropriate and controlled conditions and facilities.
11.7. Packaging systems for non-sterile devices shall maintain the integrity and cleanliness of the product and, where the devices are to be sterilised prior to use, minimise the risk of microbial contamination; the packaging system shall be suitable taking account of the method of sterilisation indicated by the manufacturer.
11.8. The labelling of the device shall distinguish between identical or similar devices placed on the market in both a sterile and a non-sterile condition additional to the symbol used to indicate that devices are sterile.
12. Devices incorporating a substance considered to be a medicinal product and devices that are composed of substances or of combinations of substances that are absorbed by or locally dispersed in the human body.
12.1. In the case of devices referred to in the first subparagraph of Article 1(8), the quality, safety and usefulness of the substance which, if used separately, would be considered to be a medicinal product within the meaning of point (2) of Article 1 of Directive 2001/83/EC, shall be verified by analogy with the methods specified in Annex I to Directive 2001/83/EC, as required by the applicable conformity assessment procedure under this Regulation.
12.2. Devices that are composed of substances or of combinations of substances that are intended to be introduced into the human body, and that are absorbed by or locally dispersed in the human body shall comply, where applicable and in a manner limited to the aspects not covered by this Regulation, with the relevant requirements laid down in Annex I to Directive 2001/83/EC for the evaluation of absorption, distribution, metabolism, excretion, local tolerance, toxicity, interaction with other devices, medicinal products or other substances and potential for adverse reactions, as required by the applicable conformity assessment procedure under this Regulation.
13. Devices incorporating materials of biological origin
13.1. For devices manufactured utilising derivatives of tissues or cells of human origin which are non-viable or are rendered non-viable covered by this Regulation in accordance with point (g) of Article 1(6), the following shall apply:
(a) donation, procurement and testing of the tissues and cells shall be done in accordance with Directive 2004/23/EC;
(b) processing, preservation and any other handling of those tissues and cells or their derivatives shall be carried out so as to provide safety for patients, users and, where applicable, other persons. In particular, safety with regard to viruses and other transmissible agents shall be addressed by appropriate methods of sourcing and by implementation of validated methods of elimination or inactivation in the course of the manufacturing process;
(c) the traceability system for those devices shall be complementary and compatible with the traceability and data protection requirements laid down in Directive 2004/23/EC and in Directive 2002/98/EC.
13.2. For devices manufactured utilising tissues or cells of animal origin, or their derivatives, which are non-viable or rendered non-viable the following shall apply:
(a) where feasible taking into account the animal species, tissues and cells of animal origin, or their derivatives, shall originate from animals that have been subjected to veterinary controls that are adapted to the intended use of the tissues. Information on the geographical origin of the animals shall be retained by manufacturers;
(b) sourcing, processing, preservation, testing and handling of tissues, cells and substances of animal origin, or their derivatives, shall be carried out so as to provide safety for patients, users and, where applicable, other persons. In particular safety with regard to viruses and other transmissible agents shall be addressed by implementation of validated methods of elimination or viral inactivation in the course of the manufacturing process, except when the use of such methods would lead to unacceptable degradation compromising the clinical benefit of the device;
(c) in the case of devices manufactured utilising tissues or cells of animal origin, or their derivatives, as referred to in Regulation (EU) No 722/2012 the particular requirements laid down in that Regulation shall apply.
13.3. For devices manufactured utilising non-viable biological substances other than those referred to in Sections 13.1 and 13.2, the processing, preservation, testing and handling of those substances shall be carried out so as to provide safety for patients, users and, where applicable, other persons, including in the waste disposal chain. In particular, safety with regard to viruses and other transmissible agents shall be addressed by appropriate methods of sourcing and by implementation of validated methods of elimination or inactivation in the course of the manufacturing process.
14. Construction of devices and interaction with their environment
14.1. If the device is intended for use in combination with other devices or equipment the whole combination, including the connection system shall be safe and shall not impair the specified performance of the devices. Any restrictions on use applying to such combinations shall be indicated on the label and/or in the instructions for use. Connections which the user has to handle, such as fluid, gas transfer, electrical or mechanical coupling, shall be designed and constructed in such a way as to minimise all possible risks, such as misconnection.
14.2. Devices shall be designed and manufactured in such a way as to remove or reduce as far as possible:
(a) the risk of injury, in connection with their physical features, including the volume/pressure ratio, dimensional and where appropriate ergonomic features;
(b) risks connected with reasonably foreseeable external influences or environmental conditions, such as magnetic fields, external electrical and electromagnetic effects, electrostatic discharge, radiation associated with diagnostic or therapeutic procedures, pressure, humidity, temperature, variations in pressure and acceleration or radio signal interferences;
(c) the risks associated with the use of the device when it comes into contact with materials, liquids, and substances, including gases, to which it is exposed during normal conditions of use;
(d) the risks associated with the possible negative interaction between software and the IT environment within which it operates and interacts;
(e) the risks of accidental ingress of substances into the device;
(f) the risks of reciprocal interference with other devices normally used in the investigations or for the treatment given; and
(g) risks arising where maintenance or calibration are not possible (as with implants), from ageing of materials used or loss of accuracy of any measuring or control mechanism.
14.3. Devices shall be designed and manufactured in such a way as to minimise the risks of fire or explosion during normal use and in single fault condition. Particular attention shall be paid to devices the intended use of which includes exposure to or use in association with flammable or explosive substances or substances which could cause combustion.
14.4. Devices shall be designed and manufactured in such a way that adjustment, calibration, and maintenance can be done safely and effectively.
14.5. Devices that are intended to be operated together with other devices or products shall be designed and manufactured in such a way that the interoperability and compatibility are reliable and safe.
14.6 Any measurement, monitoring or display scale shall be designed and manufactured in line with ergonomic principles, taking account of the intended purpose, users and the environmental conditions in which the devices are intended to be used.
14.7. Devices shall be designed and manufactured in such a way as to facilitate their safe disposal and the safe disposal of related waste substances by the user, patient or other person. To that end, manufacturers shall identify and test procedures and measures as a result of which their devices can be safely disposed after use. Such procedures shall be described in the instructions for use.
15. Devices with a diagnostic or measuring function
15.1. Diagnostic devices and devices with a measuring function, shall be designed and manufactured in such a way as to provide sufficient accuracy, precision and stability for their intended purpose, based on appropriate scientific and technical methods. The limits of accuracy shall be indicated by the manufacturer.
15.2. The measurements made by devices with a measuring function shall be expressed in legal units conforming to the provisions of Council Directive 80/181/EECCouncil Directive 80/181/EEC of 20 December 1979 on the approximation of the laws of the Member States relating to units of measurement and on the repeal of Directive 71/354/EEC (OJ L 39, 15.2.1980, p. 40)..
16. Protection against radiation
16.1. General
(a) Devices shall be designed, manufactured and packaged in such a way that exposure of patients, users and other persons to radiation is reduced as far as possible, and in a manner that is compatible with the intended purpose, whilst not restricting the application of appropriate specified levels for therapeutic and diagnostic purposes.
(b) The operating instructions for devices emitting hazardous or potentially hazardous radiation shall contain detailed information as to the nature of the emitted radiation, the means of protecting the patient and the user, and on ways of avoiding misuse and of reducing the risks inherent to installation as far as possible and appropriate. Information regarding the acceptance and performance testing, the acceptance criteria, and the maintenance procedure shall also be specified.
16.2. Intended radiation
(a) Where devices are designed to emit hazardous, or potentially hazardous, levels of ionizing and/or non-ionizing radiation necessary for a specific medical purpose the benefit of which is considered to outweigh the risks inherent to the emission, it shall be possible for the user to control the emissions. Such devices shall be designed and manufactured to ensure reproducibility of relevant variable parameters within an acceptable tolerance.
(b) Where devices are intended to emit hazardous, or potentially hazardous, ionizing and/or non-ionizing radiation, they shall be fitted, where possible, with visual displays and/or audible warnings of such emissions.
16.3. Devices shall be designed and manufactured in such a way that exposure of patients, users and other persons to the emission of unintended, stray or scattered radiation is reduced as far as possible. Where possible and appropriate, methods shall be selected which reduce the exposure to radiation of patients, users and other persons who may be affected.
16.4. Ionising radiation
(a) Devices intended to emit ionizing radiation shall be designed and manufactured taking into account the requirements of the Directive 2013/59/Euratom laying down basic safety standards for protection against the dangers arising from exposure to ionising radiation.
(b) Devices intended to emit ionising radiation shall be designed and manufactured in such a way as to ensure that, where possible, taking into account the intended use, the quantity, geometry and quality of the radiation emitted can be varied and controlled, and, if possible, monitored during treatment.
(c) Devices emitting ionising radiation intended for diagnostic radiology shall be designed and manufactured in such a way as to achieve an image and/or output quality that are appropriate to the intended medical purpose whilst minimising radiation exposure of the patient and user.
(d) Devices that emit ionising radiation and are intended for therapeutic radiology shall be designed and manufactured in such a way as to enable reliable monitoring and control of the delivered dose, the beam type, energy and, where appropriate, the quality of radiation.
17. Electronic programmable systems — devices that incorporate electronic programmable systems and software that are devices in themselves
17.1. Devices that incorporate electronic programmable systems, including software, or software that are devices in themselves, shall be designed to ensure repeatability, reliability and performance in line with their intended use. In the event of a single fault condition, appropriate means shall be adopted to eliminate or reduce as far as possible consequent risks or impairment of performance.
17.2. For devices that incorporate software or for software that are devices in themselves, the software shall be developed and manufactured in accordance with the state of the art taking into account the principles of development life cycle, risk management, including information security, verification and validation.
17.3. Software referred to in this Section that is intended to be used in combination with mobile computing platforms shall be designed and manufactured taking into account the specific features of the mobile platform (e.g. size and contrast ratio of the screen) and the external factors related to their use (varying environment as regards level of light or noise).
17.4. Manufacturers shall set out minimum requirements concerning hardware, IT networks characteristics and IT security measures, including protection against unauthorised access, necessary to run the software as intended.
18. Active devices and devices connected to them
18.1. For non-implantable active devices, in the event of a single fault condition, appropriate means shall be adopted to eliminate or reduce as far as possible consequent risks.
18.2. Devices where the safety of the patient depends on an internal power supply shall be equipped with a means of determining the state of the power supply and an appropriate warning or indication for when the capacity of the power supply becomes critical. If necessary, such warning or indication shall be given prior to the power supply becoming critical.
18.3. Devices where the safety of the patient depends on an external power supply shall include an alarm system to signal any power failure.
18.4. Devices intended to monitor one or more clinical parameters of a patient shall be equipped with appropriate alarm systems to alert the user of situations which could lead to death or severe deterioration of the patient's state of health.
18.5. Devices shall be designed and manufactured in such a way as to reduce as far as possible the risks of creating electromagnetic interference which could impair the operation of the device in question or other devices or equipment in the intended environment.
18.6. Devices shall be designed and manufactured in such a way as to provide a level of intrinsic immunity to electromagnetic interference such that is adequate to enable them to operate as intended.
18.7. Devices shall be designed and manufactured in such a way as to avoid, as far as possible, the risk of accidental electric shocks to the patient, user or any other person, both during normal use of the device and in the event of a single fault condition in the device, provided the device is installed and maintained as indicated by the manufacturer.
18.8. Devices shall be designed and manufactured in such a way as to protect, as far as possible, against unauthorised access that could hamper the device from functioning as intended.
19. Particular requirements for active implantable devices
19.1. Active implantable devices shall be designed and manufactured in such a way as to remove or minimize as far as possible:
(a) risks connected with the use of energy sources with particular reference, where electricity is used, to insulation, leakage currents and overheating of the devices,
(b) risks connected with medical treatment, in particular those resulting from the use of defibrillators or high-frequency surgical equipment, and
(c) risks which may arise where maintenance and calibration are impossible, including:
excessive increase of leakage currents,
ageing of the materials used,
excess heat generated by the device,
decreased accuracy of any measuring or control mechanism.
19.2. Active implantable devices shall be designed and manufactured in such a way as to ensure
if applicable, the compatibility of the devices with the substances they are intended to administer, and
the reliability of the source of energy.
19.3. Active implantable devices and, if appropriate, their component parts shall be identifiable to allow any necessary measure to be taken following the discovery of a potential risk in connection with the devices or their component parts.
19.4. Active implantable devices shall bear a code by which they and their manufacturer can be unequivocally identified (particularly with regard to the type of device and its year of manufacture); it shall be possible to read this code, if necessary, without the need for a surgical operation.
20. Protection against mechanical and thermal risks
20.1. Devices shall be designed and manufactured in such a way as to protect patients and users against mechanical risks connected with, for example, resistance to movement, instability and moving parts.
20.2. Devices shall be designed and manufactured in such a way as to reduce to the lowest possible level the risks arising from vibration generated by the devices, taking account of technical progress and of the means available for limiting vibrations, particularly at source, unless the vibrations are part of the specified performance.
20.3. Devices shall be designed and manufactured in such a way as to reduce to the lowest possible level the risks arising from the noise emitted, taking account of technical progress and of the means available to reduce noise, particularly at source, unless the noise emitted is part of the specified performance.
20.4. Terminals and connectors to the electricity, gas or hydraulic and pneumatic energy supplies which the user or other person has to handle, shall be designed and constructed in such a way as to minimise all possible risks.
20.5. Errors likely to be made when fitting or refitting certain parts which could be a source of risk shall be made impossible by the design and construction of such parts or, failing this, by information given on the parts themselves and/or their housings.
The same information shall be given on moving parts and/or their housings where the direction of movement needs to be known in order to avoid a risk.
20.6. Accessible parts of devices (excluding the parts or areas intended to supply heat or reach given temperatures) and their surroundings shall not attain potentially dangerous temperatures under normal conditions of use.
21. Protection against the risks posed to the patient or user by devices supplying energy or substances
21.1. Devices for supplying the patient with energy or substances shall be designed and constructed in such a way that the amount to be delivered can be set and maintained accurately enough to ensure the safety of the patient and of the user.
21.2. Devices shall be fitted with the means of preventing and/or indicating any inadequacies in the amount of energy delivered or substances delivered which could pose a danger. Devices shall incorporate suitable means to prevent, as far as possible, the accidental release of dangerous levels of energy or substances from an energy and/or substance source.
21.3. The function of the controls and indicators shall be clearly specified on the devices. Where a device bears instructions required for its operation or indicates operating or adjustment parameters by means of a visual system, such information shall be understandable to the user and, as appropriate, the patient.
22. Protection against the risks posed by medical devices intended by the manufacturer for use by lay persons
22.1. Devices for use by lay persons shall be designed and manufactured in such a way that they perform appropriately for their intended purpose taking into account the skills and the means available to lay persons and the influence resulting from variation that can be reasonably anticipated in the lay person's technique and environment. The information and instructions provided by the manufacturer shall be easy for the lay person to understand and apply.
22.2. Devices for use by lay persons shall be designed and manufactured in such a way as to:
ensure that the device can be used safely and accurately by the intended user at all stages of the procedure, if necessary after appropriate training and/or information,
reduce, as far as possible and appropriate, the risk from unintended cuts and pricks such as needle stick injuries, and
reduce as far as possible the risk of error by the intended user in the handling of the device and, if applicable, in the interpretation of the results.
22.3. Devices for use by lay persons shall, where appropriate, include a procedure by which the lay person:
can verify that, at the time of use, the device will perform as intended by the manufacturer, and
if applicable, is warned if the device has failed to provide a valid result.
CHAPTER III
REQUIREMENTS REGARDING THE INFORMATION SUPPLIED WITH THE DEVICE
23. Label and instructions for use
23.1. General requirements regarding the information supplied by the manufacturer
Each device shall be accompanied by the information needed to identify the device and its manufacturer, and by any safety and performance information relevant to the user, or any other person, as appropriate. Such information may appear on the device itself, on the packaging or in the instructions for use, and shall, if the manufacturer has a website, be made available and kept up to date on the website, taking into account the following:
(a) The medium, format, content, legibility, and location of the label and instructions for use shall be appropriate to the particular device, its intended purpose and the technical knowledge, experience, education or training of the intended user(s). In particular, instructions for use shall be written in terms readily understood by the intended user and, where appropriate, supplemented with drawings and diagrams.
(b) The information required on the label shall be provided on the device itself. If this is not practicable or appropriate, some or all of the information may appear on the packaging for each unit, and/or on the packaging of multiple devices.
(c) Labels shall be provided in a human-readable format and may be supplemented by machine-readable information, such as radio-frequency identification (RFID) or bar codes.
(d) Instructions for use shall be provided together with devices. By way of exception, instructions for use shall not be required for class I and class IIa devices if such devices can be used safely without any such instructions and unless otherwise provided for elsewhere in this Section.
(e) Where multiple devices are supplied to a single user and/or location, a single copy of the instructions for use may be provided if so agreed by the purchaser who in any case may request further copies to be provided free of charge.
(f) Instructions for use may be provided to the user in non-paper format (e.g. electronic) to the extent, and only under the conditions, set out in Regulation (EU) No 207/2012 or in any subsequent implementing rules adopted pursuant to this Regulation.
(g) Residual risks which are required to be communicated to the user and/or other person shall be included as limitations, contra-indications, precautions or warnings in the information supplied by the manufacturer.
(h) Where appropriate, the information supplied by the manufacturer shall take the form of internationally recognised symbols. Any symbol or identification colour used shall conform to the harmonised standards or CS. In areas for which no harmonised standards or CS exist, the symbols and colours shall be described in the documentation supplied with the device.
23.2. Information on the label
The label shall bear all of the following particulars:
(a) the name or trade name of the device;
(b) the details strictly necessary for a user to identify the device, the contents of the packaging and, where it is not obvious for the user, the intended purpose of the device;
(c) the name, registered trade name or registered trade mark of the manufacturer and the address of its registered place of business;
(d) if the manufacturer has its registered place of business outside the Union, the name of the authorised representative and address of the registered place of business of the authorised representative;
(e) where applicable, an indication that the device contains or incorporates:
a medicinal substance, including a human blood or plasma derivative, or
tissues or cells, or their derivatives, of human origin, or
tissues or cells of animal origin, or their derivatives, as referred to in Regulation (EU) No 722/2012;
(f) where applicable, information labelled in accordance 
[… truncated by emendrix: 11631 characters omitted …]
```

**After**

```
ANNEX I
GENERAL SAFETY AND PERFORMANCE REQUIREMENTS
CHAPTER I
GENERAL REQUIREMENTS
1. Devices shall achieve the performance intended by their manufacturer and shall be designed and manufactured in such a way that, during normal conditions of use, they are suitable for their intended purpose. They shall be safe and effective and shall not compromise the clinical condition or the safety of patients, or the safety and health of users or, where applicable, other persons, provided that any risks which may be associated with their use constitute acceptable risks when weighed against the benefits to the patient and are compatible with a high level of protection of health and safety, taking into account the generally acknowledged state of the art.
2. The requirement in this Annex to reduce risks as far as possible means the reduction of risks as far as possible without adversely affecting the benefit-risk ratio.
3. Manufacturers shall establish, implement, document and maintain a risk management system.
Risk management shall be understood as a continuous iterative process throughout the entire lifecycle of a device, requiring regular systematic updating. In carrying out risk management manufacturers shall:
(a) establish and document a risk management plan for each device;
(b) identify and analyse the known and foreseeable hazards associated with each device;
(c) estimate and evaluate the risks associated with, and occurring during, the intended use and during reasonably foreseeable misuse;
(d) eliminate or control the risks referred to in point (c) in accordance with the requirements of Section 4;
(e) evaluate the impact of information from the production phase and, in particular, from the post-market surveillance system, on hazards and the frequency of occurrence thereof, on estimates of their associated risks, as well as on the overall risk, benefit-risk ratio and risk acceptability; and
(f) based on the evaluation of the impact of the information referred to in point (e), if necessary amend control measures in line with the requirements of Section 4.
4. Risk control measures adopted by manufacturers for the design and manufacture of the devices shall conform to safety principles, taking account of the generally acknowledged state of the art. To reduce risks, Manufacturers shall manage risks so that the residual risk associated with each hazard as well as the overall residual risk is judged acceptable. In selecting the most appropriate solutions, manufacturers shall, in the following order of priority:
(a) eliminate or reduce risks as far as possible through safe design and manufacture;
(b) where appropriate, take adequate protection measures, including alarms if necessary, in relation to risks that cannot be eliminated; and
(c) provide information for safety (warnings/precautions/contra-indications) and, where appropriate, training to users.
Manufacturers shall inform users of any residual risks.
5. In eliminating or reducing risks related to use error, the manufacturer shall:
(a) reduce as far as possible the risks related to the ergonomic features of the device and the environment in which the device is intended to be used (design for patient safety), and
(b) give consideration to the technical knowledge, experience, education, training and use environment, where applicable, and the medical and physical conditions of intended users (design for lay, professional, disabled or other users).
6. The characteristics and performance of a device shall not be adversely affected to such a degree that the health or safety of the patient or the user and, where applicable, of other persons are compromised during the lifetime of the device, as indicated by the manufacturer, when the device is subjected to the stresses which can occur during normal conditions of use and has been properly maintained in accordance with the manufacturer's instructions.
7. Devices shall be designed, manufactured and packaged in such a way that their characteristics and performance during their intended use are not adversely affected during transport and storage, for example, through fluctuations of temperature and humidity, taking account of the instructions and information provided by the manufacturer.
8. All known and foreseeable risks, and any undesirable side-effects, shall be minimised and be acceptable when weighed against the evaluated benefits to the patient and/or user arising from the achieved performance of the device during normal conditions of use.
9. For the devices referred to in Annex XVI, the general safety requirements set out in Sections 1 and 8 shall be understood to mean that the device, when used under the conditions and for the purposes intended, does not present a risk at all or presents a risk that is no more than the maximum acceptable risk related to the product's use which is consistent with a high level of protection for the safety and health of persons.
CHAPTER II
REQUIREMENTS REGARDING DESIGN AND MANUFACTURE
10. Chemical, physical and biological properties
10.1. Devices shall be designed and manufactured in such a way as to ensure that the characteristics and performance requirements referred to in Chapter I are fulfilled. Particular attention shall be paid to:
(a) the choice of materials and substances used, particularly as regards toxicity and, where relevant, flammability;
(b) the compatibility between the materials and substances used and biological tissues, cells and body fluids, taking account of the intended purpose of the device and, where relevant, absorption, distribution, metabolism and excretion;
(c) the compatibility between the different parts of a device which consists of more than one implantable part;
(d) the impact of processes on material properties;
(e) where appropriate, the results of biophysical or modelling research the validity of which has been demonstrated beforehand;
(f) the mechanical properties of the materials used, reflecting, where appropriate, matters such as strength, ductility, fracture resistance, wear resistance and fatigue resistance;
(g) surface properties; and
(h) the confirmation that the device meets any defined chemical and/or physical specifications.
10.2. Devices shall be designed, manufactured and packaged in such a way as to minimise the risk posed by contaminants and residues to patients, taking account of the intended purpose of the device, and to the persons involved in the transport, storage and use of the devices. Particular attention shall be paid to tissues exposed to those contaminants and residues and to the duration and frequency of exposure.
10.3. Devices shall be designed and manufactured in such a way that they can be used safely with the materials and substances, including gases, with which they enter into contact during their intended use; if the devices are intended to administer medicinal products they shall be designed and manufactured in such a way as to be compatible with the medicinal products concerned in accordance with the provisions and restrictions governing those medicinal products and that the performance of both the medicinal products and of the devices is maintained in accordance with their respective indications and intended use.
10.4. Substances
10.4.1. Design and manufacture of devices
Devices shall be designed and manufactured in such a way as to reduce as far as possible the risks posed by substances or particles, including wear debris, degradation products and processing residues, that may be released from the device.
Devices, or those parts thereof or those materials used therein that:
are invasive and come into direct contact with the human body,
(re)administer medicines, body liquids or other substances, including gases, to/from the body, or
transport or store such medicines, body fluids or substances, including gases, to be (re)administered to the body,
shall only contain the following substances in a concentration that is above 0,1 % weight by weight (w/w) where justified pursuant to Section 10.4.2:
(a) substances which are carcinogenic, mutagenic or toxic to reproduction (CMR), of category 1A or 1B, in accordance with Part 3 of Annex VI to Regulation (EC) No 1272/2008 of the European Parliament and of the CouncilRegulation (EC) No 1272/2008 of the European Parliament and of the Council of 16 December 2008 on classification, labelling and packaging of substances and mixtures, amending and repealing Directives 67/548/EEC and 1999/45/EC, and amending Regulation (EC) No 1907/2006 ( OJ L 353, 31.12.2008, p. 1)., or
(b) substances which are classified as endocrine disruptors for human health, of Category 1, in accordance with Part 3 of Annex VI to Regulation (EC) No 1272/2008 of the European Parliament and of the CouncilRegulation (EC) No 1272/2008 of the European Parliament and of the Council of 16 December 2008 on classification, labelling and packaging of substances and mixtures, amending and repealing Directives 67/548/EEC and 1999/45/EC, and amending Regulation (EC) No 1907/2006 (OJ L 353, 31.12.2008, p. 1, ELI: http://data.europa.eu/eli/reg/2008/1272/oj). and substances having endocrine-disrupting properties for which there is scientific evidence of probable serious effects to human health and which are identified in accordance with the procedure set out in Article 59 of Regulation (EC) No 1907/2006 of the European Parliament and of the CouncilRegulation (EC) No 1907/2006 of the European Parliament and of the Council of 18 December 2006 concerning the Registration, Evaluation, Authorisation and Restriction of Chemicals (REACH), establishing a European Chemicals Agency, amending Directive 1999/45/EC and repealing Council Regulation (EEC) No 793/93 and Commission Regulation (EC) No 1488/94 as well as Council Directive 76/769/EEC and Commission Directives 91/155/EEC, 93/67/EEC, 93/105/EC and 2000/21/EC (OJ L 396, 30.12.2006, p. 1, ELI: http://data.europa.eu/eli/reg/2006/1907/oj). or substances having endocrine-disrupting properties relevant to human health identified in accordance with Regulation (EU) No 528/2012 of the European Parliament and the CouncilRegulation (EU) No 528/2012 of the European Parliament and the Council of 22 May 2012 concerning the making available on the market of and use of biocidal products (OJ L 167, 27.6.2012, p. 1, ELI: http://data.europa.eu/eli/reg/2012/528/oj)..
10.4.2. Justification regarding the presence of CMR and/or endocrine-disrupting substances
The justification for the presence of such substances shall be based upon:
(a) an analysis and estimation of potential patient or user exposure to the substance;
(b) an analysis of possible alternative substances, materials or designs, including, where available, information about independent research, peer-reviewed studies, scientific opinions from relevant scientific committees and an analysis of the availability of such alternatives;
(c) argumentation as to why possible substance and/ or material substitutes, if available, or design changes, if feasible, are inappropriate in relation to maintaining the functionality, performance and the benefit-risk ratios of the product; including taking into account if the intended use of such devices includes treatment of children or treatment of pregnant or breastfeeding women or treatment of other patient groups considered particularly vulnerable to such substances and/or materials; and
(d) where applicable and available, the latest relevant guidelines in accordance with Sections 10.4.3 and 10.4.4.
10.4.3. Guidelines on phthalates
When deemed appropriate based on the latest scientific evidence, but at least every 5 years, the Commission shall request the European Chemicals Agency (ECHA) to prepare and update guidelines on the benefit-risk assessment of the presence of phthalates which belong to either of the groups of substances referred to in Section 10.4.1, points (a) and (b). The benefit-risk assessment shall consider the intended purpose and context of the use of the device, as well as any available alternative substances and alternative materials, designs or medical treatments.
When appropriate or when requested by the Commission, the ECHA shall consult the Committee for Risk Assessment and the Committee for Socio-economic Analysis.
10.4.4. Guidelines on other CMR and endocrine-disrupting substances
In addition to the guidelines referred to in Section 10.4.3, the Commission shall request the ECHA to prepare such guidelines for other substances referred to in Section 10.4.1, points (a) and (b), where appropriate. Such guidelines shall be prepared in accordance with the process described in Section 10.4.3.
10.4.5. Labelling
Where devices, parts thereof or materials used therein as referred to in Section 10.4.1. contain substances referred to in points (a) or (b) of Section 10.4.1. in a concentration above 0,1 % weight by weight (w/w), the presence of those substances shall be labelled on the device itself and/or on the packaging for each unit or, where appropriate, on the sales packaging, with the list of such substances. If the intended use of such devices includes treatment of children or treatment of pregnant or breastfeeding women or treatment of other patient groups considered particularly vulnerable to such substances and/or materials, information on residual risks for those patient groups and, if applicable, on appropriate precautionary measures shall be given in the instructions for use.
10.5. Devices shall be designed and manufactured in such a way as to reduce as far as possible the risks posed by the unintentional ingress of substances into the device taking into account the device and the nature of the environment in which it is intended to be used.
10.6. Devices shall be designed and manufactured in such a way as to reduce as far as possible the risks linked to the size and the properties of particles which are or can be released into the patient's or user's body, unless they come into contact with intact skin only. Special attention shall be given to nanomaterials.
11. Infection and microbial contamination
11.1. Devices and their manufacturing processes shall be designed in such a way as to eliminate or to reduce as far as possible the risk of infection to patients, users and, where applicable, other persons. The design shall:
(a) reduce as far as possible and appropriate the risks from unintended cuts and pricks, such as needle stick injuries,
(b) allow easy and safe handling,
(c) reduce as far as possible any microbial leakage from the device and/or microbial exposure during use, and
(d) prevent microbial contamination of the device or its content such as specimens or fluids.
11.2. Where necessary devices shall be designed to facilitate their safe cleaning, disinfection, and/or re-sterilisation.
11.3. Devices labelled as having a specific microbial state shall be designed, manufactured and packaged to ensure that they remain in that state when placed on the market and remain so under the transport and storage conditions specified by the manufacturer.
11.4. Devices delivered in a sterile state shall be designed, manufactured and packaged in accordance with appropriate procedures, to ensure that they are sterile when placed on the market and that, unless the packaging which is intended to maintain their sterile condition is damaged, they remain sterile, under the transport and storage conditions specified by the manufacturer, until that packaging is opened at the point of use. It shall be ensured that the integrity of that packaging is clearly evident to the final user.
11.5. Devices labelled as sterile shall be processed, manufactured, packaged and, sterilised by means of appropriate, validated methods.
11.6. Devices intended to be sterilised shall be manufactured and packaged in appropriate and controlled conditions and facilities.
11.7. Packaging systems for non-sterile devices shall maintain the integrity and cleanliness of the product and, where the devices are to be sterilised prior to use, minimise the risk of microbial contamination; the packaging system shall be suitable taking account of the method of sterilisation indicated by the manufacturer.
11.8. The labelling of the device shall distinguish between identical or similar devices placed on the market in both a sterile and a non-sterile condition additional to the symbol used to indicate that devices are sterile.
12. Devices incorporating a substance considered to be a medicinal product and devices that are composed of substances or of combinations of substances that are absorbed by or locally dispersed in the human body.
12.1. In the case of devices referred to in the first subparagraph of Article 1(8), the quality, safety and usefulness of the substance which, if used separately, would be considered to be a medicinal product within the meaning of point (2) of Article 1 of Directive 2001/83/EC, shall be verified by analogy with the methods specified in Annex I to Directive 2001/83/EC, as required by the applicable conformity assessment procedure under this Regulation.
12.2. Devices that are composed of substances or of combinations of substances that are intended to be introduced into the human body, and that are absorbed by or locally dispersed in the human body shall comply, where applicable and in a manner limited to the aspects not covered by this Regulation, with the relevant requirements laid down in Annex I to Directive 2001/83/EC for the evaluation of absorption, distribution, metabolism, excretion, local tolerance, toxicity, interaction with other devices, medicinal products or other substances and potential for adverse reactions, as required by the applicable conformity assessment procedure under this Regulation.
13. Devices incorporating materials of biological origin
13.1. For devices manufactured utilising derivatives of tissues or cells of human origin which are non-viable or are rendered non-viable covered by this Regulation in accordance with point (g) of Article 1(6), the following shall apply:
(a) donation, procurement and testing of the tissues and cells shall be done in accordance with Directive 2004/23/EC;
(b) processing, preservation and any other handling of those tissues and cells or their derivatives shall be carried out so as to provide safety for patients, users and, where applicable, other persons. In particular, safety with regard to viruses and other transmissible agents shall be addressed by appropriate methods of sourcing and by implementation of validated methods of elimination or inactivation in the course of the manufacturing process;
(c) the traceability system for those devices shall be complementary and compatible with the traceability and data protection requirements laid down in Directive 2004/23/EC and in Directive 2002/98/EC.
13.2. For devices manufactured utilising tissues or cells of animal origin, or their derivatives, which are non-viable or rendered non-viable the following shall apply:
(a) where feasible taking into account the animal species, tissues and cells of animal origin, or their derivatives, shall originate from animals that have been subjected to veterinary controls that are adapted to the intended use of the tissues. Information on the geographical origin of the animals shall be retained by manufacturers;
(b) sourcing, processing, preservation, testing and handling of tissues, cells and substances of animal origin, or their derivatives, shall be carried out so as to provide safety for patients, users and, where applicable, other persons. In particular safety with regard to viruses and other transmissible agents shall be addressed by implementation of validated methods of elimination or viral inactivation in the course of the manufacturing process, except when the use of such methods would lead to unacceptable degradation compromising the clinical benefit of the device;
(c) in the case of devices manufactured utilising tissues or cells of animal origin, or their derivatives, as referred to in Regulation (EU) No 722/2012 the particular requirements laid down in that Regulation shall apply.
13.3. For devices manufactured utilising non-viable biological substances other than those referred to in Sections 13.1 and 13.2, the processing, preservation, testing and handling of those substances shall be carried out so as to provide safety for patients, users and, where applicable, other persons, including in the waste disposal chain. In particular, safety with regard to viruses and other transmissible agents shall be addressed by appropriate methods of sourcing and by implementation of validated methods of elimination or inactivation in the course of the manufacturing process.
14. Construction of devices and interaction with their environment
14.1. If the device is intended for use in combination with other devices or equipment the whole combination, including the connection system shall be safe and shall not impair the specified performance of the devices. Any restrictions on use applying to such combinations shall be indicated on the label and/or in the instructions for use. Connections which the user has to handle, such as fluid, gas transfer, electrical or mechanical coupling, shall be designed and constructed in such a way as to minimise all possible risks, such as misconnection.
14.2. Devices shall be designed and manufactured in such a way as to remove or reduce as far as possible:
(a) the risk of injury, in connection with their physical features, including the volume/pressure ratio, dimensional and where appropriate ergonomic features;
(b) risks connected with reasonably foreseeable external influences or environmental conditions, such as magnetic fields, external electrical and electromagnetic effects, electrostatic discharge, radiation associated with diagnostic or therapeutic procedures, pressure, humidity, temperature, variations in pressure and acceleration or radio signal interferences;
(c) the risks associated with the use of the device when it comes into contact with materials, liquids, and substances, including gases, to which it is exposed during normal conditions of use;
(d) the risks associated with the possible negative interaction between software and the IT environment within which it operates and interacts;
(e) the risks of accidental ingress of substances into the device;
(f) the risks of reciprocal interference with other devices normally used in the investigations or for the treatment given; and
(g) risks arising where maintenance or calibration are not possible (as with implants), from ageing of materials used or loss of accuracy of any measuring or control mechanism.
14.3. Devices shall be designed and manufactured in such a way as to minimise the risks of fire or explosion during normal use and in single fault condition. Particular attention shall be paid to devices the intended use of which includes exposure to or use in association with flammable or explosive substances or substances which could cause combustion.
14.4. Devices shall be designed and manufactured in such a way that adjustment, calibration, and maintenance can be done safely and effectively.
14.5. Devices that are intended to be operated together with other devices or products shall be designed and manufactured in such a way that the interoperability and compatibility are reliable and safe.
14.6 Any measurement, monitoring or display scale shall be designed and manufactured in line with ergonomic principles, taking account of the intended purpose, users and the environmental conditions in which the devices are intended to be used.
14.7. Devices shall be designed and manufactured in such a way as to facilitate their safe disposal and the safe disposal of related waste substances by the user, patient or other person. To that end, manufacturers shall identify and test procedures and measures as a result of which their devices can be safely disposed after use. Such procedures shall be described in the instructions for use.
15. Devices with a diagnostic or measuring function
15.1. Diagnostic devices and devices with a measuring function, shall be designed and manufactured in such a way as to provide sufficient accuracy, precision and stability for their intended purpose, based on appropriate scientific and technical methods. The limits of accuracy shall be indicated by the manufacturer.
15.2. The measurements made by devices with a measuring function shall be expressed in legal units conforming to the provisions of Council Directive 80/181/EECCouncil Directive 80/181/EEC of 20 December 1979 on the approximation of the laws of the Member States relating to units of measurement and on the repeal of Directive 71/354/EEC (OJ L 39, 15.2.1980, p. 40)..
16. Protection against radiation
16.1. General
(a) Devices shall be designed, manufactured and packaged in such a way that exposure of patients, users and other persons to radiation is reduced as far as possible, and in a manner that is compatible with the intended purpose, whilst not restricting the application of appropriate specified levels for therapeutic and diagnostic purposes.
(b) The operating instructions for devices emitting hazardous or potentially hazardous radiation shall contain detailed information as to the nature of the emitted radiation, the means of protecting the patient and the user, and on ways of avoiding misuse and of reducing the risks inherent to installation as far as possible and appropriate. Information regarding the acceptance and performance testing, the acceptance criteria, and the maintenance procedure shall also be specified.
16.2. Intended radiation
(a) Where devices are designed to emit hazardous, or potentially hazardous, levels of ionizing and/or non-ionizing radiation necessary for a specific medical purpose the benefit of which is considered to outweigh the risks inherent to the emission, it shall be possible for the user to control the emissions. Such devices shall be designed and manufactured to ensure reproducibility of relevant variable parameters within an acceptable tolerance.
(b) Where devices are intended to emit hazardous, or potentially hazardous, ionizing and/or non-ionizing radiation, they shall be fitted, where possible, with visual displays and/or audible warnings of such emissions.
16.3. Devices shall be designed and manufactured in such a way that exposure of patients, users and other persons to the emission of unintended, stray or scattered radiation is reduced as far as possible. Where possible and appropriate, methods shall be selected which reduce the exposure to radiation of patients, users and other persons who may be affected.
16.4. Ionising radiation
(a) Devices intended to emit ionizing radiation shall be designed and manufactured taking into account the requirements of the Directive 2013/59/Euratom laying down basic safety standards for protection against the dangers arising from exposure to ionising radiation.
(b) Devices intended to emit ionising radiation shall be designed and manufactured in such a way as to ensure that, where possible, taking into account the intended use, the quantity, geometry and quality of the radiation emitted can be varied and controlled, and, if possible, monitored during treatment.
(c) Devices emitting ionising radiation intended for diagnostic radiology shall be designed and manufactured in such a way as to achieve an image and/or output quality that are appropriate to the intended medical purpose whilst minimising radiation exposure of the patient and user.
(d) Devices that emit ionising radiation and are intended for therapeutic radiology shall be designed and manufactured in such a way as to enable reliable monitoring and control of the delivered dose, the beam type, energy and, where appropriate, the quality of radiation.
17. Electronic programmable systems — devices that incorporate electronic programmable systems and software that are devices in themselves
17.1. Devices that incorporate electronic programmable systems, including software, or software that are devices in themselves, shall be designed to ensure repeatability, reliability and performance in line with their intended use. In the event of a single fault condition, appropriate means shall be adopted to eliminate or reduce as far as possible consequent risks or impairment of performance.
17.2. For devices that incorporate software or for software that are devices in themselves, the software shall be developed and manufactured in accordance with the state of the art taking into account the principles of development life cycle, risk management, including information security, verification and validation.
17.3. Software referred to in this Section that is intended to be used in combination with mobile computing platforms shall be designed and manufactured taking into account the specific features of the mobile platform (e.g. size and contrast ratio of the screen) and the external factors related to their use (varying environment as regards level of light or noise).
17.4. Manufacturers shall set out minimum requirements concerning hardware, IT networks characteristics and IT security measures, including protection against unauthorised access, necessary to run the software as intended.
18. Active devices and devices connected to them
18.1. For non-implantable active devices, in the event of a single fault condition, appropriate means shall be adopted to eliminate or reduce as far as possible consequent risks.
18.2. Devices where the safety of the patient depends on an internal power supply shall be equipped with a means of determining the state of the power supply and an appropriate warning or indication for when the capacity of the power supply becomes critical. If necessary, such warning or indication shall be given prior to the power supply becoming critical.
18.3. Devices where the safety of the patient depends on an external power supply shall include an alarm system to signal any power failure.
18.4. Devices intended to monitor one or more clinical parameters of a patient shall be equipped with appropriate alarm systems to alert the user of situations which could lead to death or severe deterioration of the patient's state of health.
18.5. Devices shall be designed and manufactured in such a way as to reduce as far as possible the risks of creating electromagnetic interference which could impair the operation of the device in question or other devices or equipment in the intended environment.
18.6. Devices shall be designed and manufactured in such a way as to provide a level of intrinsic immunity to electromagnetic interference such that is adequate to enable them to operate as intended.
18.7. Devices shall be designed and manufactured in such a way as to avoid, as far as possible, the risk of accidental electric shocks to the patient, user or any other person, both during normal use of the device and in the event of a single fault condition in the device, provided the device is installed and maintained as indicated by the manufacturer.
18.8. Devices shall be designed and manufactured in such a way as to protect, as far as possible, against unauthorised access that could hamper the device from functioning as intended.
19. Particular requirements for active implantable devices
19.1. Active implantable devices shall be designed and manufactured in such a way as to remove or minimize as far as possible:
(a) risks connected with the use of energy sources with particular reference, where electricity is used, to insulation, leakage currents and overheating of the devices,
(b) risks connected with medical treatment, in particular those resulting from the use of defibrillators or high-frequency surgical equipment, and
(c) risks which may arise where maintenance and calibration are impossible, including:
excessive increase of leakage currents,
ageing of the materials used,
excess heat generated by the device,
decreased accuracy of any measuring or control mechanism.
19.2. Active implantable devices shall be designed and manufactured in such a way as to ensure
if applicable, the compatibility of the devices with the substances they are intended to administer, and
the reliability of the source of energy.
19.3. Active implantable devices and, if appropriate, their component parts shall be identifiable to allow any necessary measure to be taken following the discovery of a potential risk in connection with the devices or their component parts.
19.4. Active implantable devices shall bear a code by which they and their manufacturer can be unequivocally identified (particularly with regard to the type of device and its year of manufacture); it shall be possible to read this code, if necessary, without the need for a surgical operation.
20. Protection against mechanical and thermal risks
20.1. Devices shall be designed and manufactured in such a way as to protect patients and users against mechanical risks connected with, for example, resistance to movement, instability and moving parts.
20.2. Devices shall be designed and manufactured in such a way as to reduce to the lowest possible level the risks arising from vibration generated by the devices, taking account of technical progress and of the means available for limiting vibrations, particularly at source, unless the vibrations are part of the specified performance.
20.3. Devices shall be designed and manufactured in such a way as to reduce to the lowest possible level the risks arising from the noise emitted, taking account of technical progress and of the means available to reduce noise, particularly at source, unless the noise emitted is part of the specified performance.
20.4. Terminals and connectors to the electricity, gas or hydraulic and pneumatic energy supplies which the user or other person has to handle, shall be designed and constructed in such a way as to minimise all possible risks.
20.5. Errors likely to be made when fitting or refitting certain parts which could be a source of risk shall be made impossible by the design and construction of such parts or, failing this, by information given on the parts themselves and/or their housings.
The same information shall be given on moving parts and/or their housings where the direction of movement needs to be known in order to avoid a risk.
20.6. Accessible parts of devices (excluding the parts or areas intended to supply heat or reach given temperatures) and their surroundings shall not attain potentially dangerous temperatures under normal conditions of use.
21. Protection against the risks posed to the patient or user by devices supplying energy or substances
21.1. Devices for supplying the patient with energy or substances shall be designed and constructed in such a way that the amount to be delivered can be set and maintained accurately enough to ensure the safety of the patient and of the user.
21.2. Devices shall be fitted with the means of preventing and/or indicating any inadequacies in the amount of energy delivered or substances delivered which could pose a danger. Devices shall incorporate suitable means to prevent, as far as possible, the accidental release of dangerous levels of energy or substances from an energy and/or substance source.
21.3. The function of the controls and indicators shall be clearly specified on the devices. Where a device bears instructions required for its operation or indicates operating or adjustment parameters by means of a visual system, such information shall be understandable to the user and, as appropriate, the patient.
22. Protection against the risks posed by medical devices intended by the manufacturer for use by lay persons
22.1. Devices for use by lay persons shall be designed and manufactured in such a way that they perform appropriately for their intended purpose taking into account the skills and the means available to lay persons and the influence resulting from variation that can be reasonably anticipated in the lay person's technique and environment. The information and instructions provided by the manufacturer shall be easy for the lay person to understand and apply.
22.2. Devices for use by lay persons shall be designed and manufactured in such a way as to:
ensure that the device can be used safely and accurately by the intended user at all stages of the procedure, if necessary after appropriate training and/or information,
reduce, as far as possible and appropriate, the risk from unintended cuts and pricks such as needle stick injuries, and
reduce as far as possible the risk of error by the intended user in the handling of the device and, if applicable, in the interpretation of the results.
22.3. Devices for use by lay persons shall, where appropriate, include a procedure by which the lay person:
can verify that, at the time of use, the device will perform as intended by the manufacturer, and
if applicable, is warned if the device has failed to provide a valid result.
CHAPTER III
REQUIREMENTS REGARDING THE INFORMATION SUPPLIED WITH THE DEVICE
23. Label and instructions for use
23.1. General requirements regarding the information supplied by the manufacturer
Each device shall be accompanied by the information needed to identify the device and its manufacturer, and by any safety and performance information relevant to the user, or any other person, as appropriate. Such information may appear on the device itself, on the packaging or in the instructions for use, and shall, if the manufacturer has a website, be made available and kept up to date on the website, taking into account the following:
(a) The medium, format, content, legibility, and location of the label and instructions for use shall be appropriate to the particular device, its intended purpose and the technical knowledge, experience, education or training of the intended user(s). In particular, instructions for use shall be written in terms readily understood by the intended user and, where appropriate, supplemented with drawings and diagrams.
(b) The information required on the label shall be provided on the device itself. If this is not practicable or appropriate, some or all of the information may appear on the packaging for each unit, and/or on the packaging of multiple devices.
(c) Labels shall be provided in a human-readable format and may be supplemented by machine-readable information, such as radio-frequency identification (RFID) or bar codes.
(d) Instructions for use shall be provided together with devices. By way of exception, instructions for use shall not be required for class I and class IIa devices if such devices can be used safely without any such instructions and unless otherwise provided for elsewhere in this Section.
(e) Where multiple devices are supplied to a single user and/or location, a single copy of the instructions for use may be provided if so agreed by the purchaser who in any case may request further copies to be provided free of charge.
(f) Instructions for use may be provided to the user in non-paper format (e.g. electronic) to the extent, and only under the conditions, set out in Regulation (EU) No 207/2012 or in any subsequent implementing rules adopted pursuant to this Regulation.
(g) Residual risks which are required to be communicated to the user and/or other person shall be included as limitations, contra-indications, precautions or warnings in the information supplied by the manufacturer.
(h) Where appropriate, the information supplied by the manufacturer shall take the form of internationally recognised symbols. Any symbol or identification colour used shall conform to the harmonised standards or CS. In areas for which no harmonised standards or CS exist, the symbols and colours shall be described in the documentation supplied with the device.
23.2. Information on the label
The label shall bear all of the following particulars:
(a) the name or trade name of the device;
(b) the details strictly necessary for a user to identify the device, the contents o
[… truncated by emendrix: 12435 characters omitted …]
```

**Shipped sentences**

1. Section 10.4.1(b) now identifies endocrine-disrupting substances by reference to Category 1 classification under Part 3 of Annex VI to Regulation (EC) No 1272/2008, in addition to substances identified under Article 59 of Regulation (EC) No 1907/2006 or under Regulation (EU) No 528/2012, replacing the earlier text that relied only on the REACH Article 59 procedure or a Commission delegated act under the Biocidal Products Regulation.
2. Section 10.4.2(d) now refers to the latest relevant guidelines generally rather than specifically to scientific committee guidelines.
3. Sections 10.4.3 and 10.4.4 no longer set the fixed 26 May 2018 and 26 May 2020 dates for mandating a scientific committee to prepare phthalate guidelines, and instead describe the Commission requesting the European Chemicals Agency to prepare and update such guidelines when deemed appropriate based on the latest scientific evidence but at least every five years, with a new reference to ECHA consulting the Committee for Risk Assessment and the Committee for Socio-economic Analysis, and Section 10.4.4 now describes the Commission requesting ECHA, rather than mandating the scientific committee, to prepare guidelines for other CMR and endocrine-disrupting substances.

- [ ] Faithful
- [ ] Not faithful — reason: 

---

**Not legal advice.** These figures describe agreement between machine-computed readings of published legal texts. They say nothing about whether any change matters to anyone, and nothing here is a substitute for reading the official consolidated text on EUR-Lex or for professional legal counsel.
