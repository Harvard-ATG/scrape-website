# At-risk document canonicalization sample

Resolves whether corpus 'at-risk' docs are real orphans or found_on artifacts (non-canonical /node//index.php referrers whose canonical IS in the sitemap). Sample fetches found_on, follows redirects.

| Host | At-risk total | Sampled | Recoverable | True-orphan | Dead | Est. true orphans |
|---|---:|---:|---:|---:|---:|---:|
| sociology.fas.harvard.edu | 614 | 40 | 0% | 100% | 0 | 614 |
| www.economics.harvard.edu | 606 | 40 | 0% | 100% | 0 | 606 |
| history.fas.harvard.edu | 583 | 40 | 0% | 100% | 0 | 583 |
| statistics.fas.harvard.edu | 363 | 40 | 0% | 100% | 0 | 363 |
| linguistics.fas.harvard.edu | 179 | 40 | 0% | 100% | 0 | 179 |
| english.fas.harvard.edu | 160 | 40 | 0% | 100% | 0 | 160 |
| astronomy.fas.harvard.edu | 115 | 40 | 0% | 100% | 0 | 115 |
| ofa.fas.harvard.edu | 115 | 40 | 0% | 100% | 0 | 115 |
| dso.college.harvard.edu | 82 | 40 | 0% | 100% | 0 | 82 |
| anthropology.fas.harvard.edu | 74 | 40 | 0% | 100% | 0 | 74 |

## Examples

### www.economics.harvard.edu
**true_orphan:**
- `http://www.economics.harvard.edu/sites/g/files/omnuum5991/files/econ/files/2023.12.01_ravenna-freeman_academic_misconduct_presentation_public.pptx` <- `http://www.economics.harvard.edu/search?search=Public&page=42` -> `https://www.economics.harvard.edu/search?search=Public&page=42`
- `https://www.economics.harvard.edu/sites/g/files/omnuum5991/files/econ/files/2021-2022_writing_and_theory_courses_all_electives_v1_0.xlsx` <- `https://www.economics.harvard.edu/search?search=Theory&page=33` -> `https://www.economics.harvard.edu/search?search=Theory&page=33`
- `https://www.economics.harvard.edu/sites/g/files/omnuum5991/files/econ/files/2022-2023_writing_and_theory_courses_all_electives_v1_2.xlsx` <- `https://www.economics.harvard.edu/search?search=Theory&page=31` -> `https://www.economics.harvard.edu/search?search=Theory&page=31`
- `https://www.economics.harvard.edu/sites/g/files/omnuum5991/files/econ/files/2022.11.02_abstractbio_yu-shule_chinasbbi_seminar_how_robots_impact_labor_relations_0.docx` <- `https://www.economics.harvard.edu/search?search=Seminars&page=187` -> `https://www.economics.harvard.edu/search?search=Seminars&page=187`
- `https://www.economics.harvard.edu/sites/g/files/omnuum5991/files/econ/files/2023.10.13_abstractbio_kozlowski_sbbi-seminar.docx` <- `https://www.economics.harvard.edu/search?search=Seminars&page=179` -> `https://www.economics.harvard.edu/search?search=Seminars&page=179`
- `https://www.economics.harvard.edu/sites/g/files/omnuum5991/files/econ/files/2023_smolin_yamashita.pdf` <- `https://www.economics.harvard.edu/search?page=365` -> `https://www.economics.harvard.edu/search?page=365`

### history.fas.harvard.edu
**true_orphan:**
- `http://history.fas.harvard.edu/sites/g/files/omnuum4421/files/%5Bvsite%3Asite-purl%5D/files/history_97_promo_material_spring_2020.pdf` <- `http://history.fas.harvard.edu/search?page=370` -> `https://history.fas.harvard.edu/search?page=370`
- `http://history.fas.harvard.edu/sites/g/files/omnuum4421/files/history/files/2024-2025_cross-listed_courses_9.xlsx` <- `http://history.fas.harvard.edu/search?page=315` -> `https://history.fas.harvard.edu/search?page=315`
- `http://history.fas.harvard.edu/sites/g/files/omnuum4421/files/history/files/charles_maier.pdf` <- `http://history.fas.harvard.edu/search?page=368` -> `https://history.fas.harvard.edu/search?page=368`
- `http://history.fas.harvard.edu/sites/g/files/omnuum4421/files/history/files/cornell_international_affairs_review_ciar_spring_2020.pdf` <- `http://history.fas.harvard.edu/search?search=International&page=4` -> `https://history.fas.harvard.edu/search?search=International&page=4`
- `http://history.fas.harvard.edu/sites/g/files/omnuum4421/files/history/files/cross-listed_courses_2014-15.pdf` <- `http://history.fas.harvard.edu/search?source=post_page---top_nav_layout_nav-----------------------------------------&page=247` -> `https://history.fas.harvard.edu/search?source=post_page---top_nav_layout_nav-----------------------------------------&page=247`
- `http://history.fas.harvard.edu/sites/g/files/omnuum4421/files/history/files/cross-listed_courses_for_2023-2024_0.pdf` <- `http://history.fas.harvard.edu/search?page=158` -> `https://history.fas.harvard.edu/search?page=158`

### sociology.fas.harvard.edu
**true_orphan:**
- `http://sociology.fas.harvard.edu/sites/g/files/omnuum1481/files/%5Bvsite%3Asite-purl%5D/files/teaching_fellow_history_2010-2018.pdf` <- `http://sociology.fas.harvard.edu/search?page=90` -> `https://sociology.fas.harvard.edu/search?page=90`
- `http://sociology.fas.harvard.edu/sites/g/files/omnuum1481/files/sociology/files/2015_16_department_course_listing_2015.08.23.pdf` <- `http://sociology.fas.harvard.edu/search?page=106` -> `https://sociology.fas.harvard.edu/search?page=106`
- `http://sociology.fas.harvard.edu/sites/g/files/omnuum1481/files/sociology/files/2015_16_department_course_listing_spring_0.pdf` <- `http://sociology.fas.harvard.edu/search?page=70` -> `https://sociology.fas.harvard.edu/search?page=70`
- `http://sociology.fas.harvard.edu/sites/g/files/omnuum1481/files/sociology/files/98ha.pdf` <- `http://sociology.fas.harvard.edu/search?page=61` -> `https://sociology.fas.harvard.edu/search?page=61`
- `http://sociology.fas.harvard.edu/sites/g/files/omnuum1481/files/sociology/files/advising_sheet_-_final.pdf` <- `http://sociology.fas.harvard.edu/search?page=116` -> `https://sociology.fas.harvard.edu/search?page=116`
- `http://sociology.fas.harvard.edu/sites/g/files/omnuum1481/files/sociology/files/cas_student_funding_opportunities_2014.pdf` <- `http://sociology.fas.harvard.edu/search?page=80` -> `https://sociology.fas.harvard.edu/search?page=80`

### statistics.fas.harvard.edu
**true_orphan:**
- `https://statistics.fas.harvard.edu/sites/g/files/omnuum10116/files/2024-dad-editedphoto1.pdf` <- `https://statistics.fas.harvard.edu/search?page=153` -> `https://statistics.fas.harvard.edu/search?page=153`
- `https://statistics.fas.harvard.edu/sites/g/files/omnuum10116/files/statistics-2/files/agresti08.pdf` <- `https://statistics.fas.harvard.edu/search?page=139` -> `https://statistics.fas.harvard.edu/search?page=139`
- `https://statistics.fas.harvard.edu/sites/g/files/omnuum10116/files/statistics-2/files/baines10.pdf` <- `https://statistics.fas.harvard.edu/search?page=174` -> `https://statistics.fas.harvard.edu/search?page=174`
- `https://statistics.fas.harvard.edu/sites/g/files/omnuum10116/files/statistics-2/files/bickel14.pdf` <- `https://statistics.fas.harvard.edu/search?page=173` -> `https://statistics.fas.harvard.edu/search?page=173`
- `https://statistics.fas.harvard.edu/sites/g/files/omnuum10116/files/statistics-2/files/blyth09.pdf` <- `https://statistics.fas.harvard.edu/search?page=138` -> `https://statistics.fas.harvard.edu/search?page=138`
- `https://statistics.fas.harvard.edu/sites/g/files/omnuum10116/files/statistics-2/files/calderhead15.pdf` <- `https://statistics.fas.harvard.edu/search?page=172` -> `https://statistics.fas.harvard.edu/search?page=172`

### linguistics.fas.harvard.edu
**true_orphan:**
- `https://linguistics.fas.harvard.edu/sites/g/files/omnuum5001/files/2025-02/Rothstein-Dowden%20Abstract_0.pdf` <- `https://linguistics.fas.harvard.edu/search?page=46` -> `https://linguistics.fas.harvard.edu/search?page=46`
- `https://linguistics.fas.harvard.edu/sites/g/files/omnuum5001/files/2025-08/Fall%202025%20Course%20Schedule%20DRAFT%20KBP%208.28.pdf` <- `https://linguistics.fas.harvard.edu/search?page=47` -> `https://linguistics.fas.harvard.edu/search?page=47`
- `https://linguistics.fas.harvard.edu/sites/g/files/omnuum5001/files/2026-03/Fall%202026%20Course%20Schedule-DRAFT%203.18.pdf` <- `https://linguistics.fas.harvard.edu/search?page=148` -> `https://linguistics.fas.harvard.edu/search?page=148`
- `https://linguistics.fas.harvard.edu/sites/g/files/omnuum5001/files/linguistics/files/2022_spring_reception_invitation_edited.pdf` <- `https://linguistics.fas.harvard.edu/search?page=137` -> `https://linguistics.fas.harvard.edu/search?page=137`
- `https://linguistics.fas.harvard.edu/sites/g/files/omnuum5001/files/linguistics/files/coppola_abstract.pdf` <- `https://linguistics.fas.harvard.edu/search?page=131` -> `https://linguistics.fas.harvard.edu/search?page=131`
- `https://linguistics.fas.harvard.edu/sites/g/files/omnuum5001/files/linguistics/files/fall_2016_course_chart_6.22.16.doc` <- `https://linguistics.fas.harvard.edu/search?page=128` -> `https://linguistics.fas.harvard.edu/search?page=128`

### english.fas.harvard.edu
**true_orphan:**
- `https://english.fas.harvard.edu/sites/g/files/omnuum1611/files/english/files/2018_perspectives_final_webready.pdf` <- `https://english.fas.harvard.edu/search?page=90` -> `https://english.fas.harvard.edu/search?page=90`
- `https://english.fas.harvard.edu/sites/g/files/omnuum1611/files/english/files/_course_listing_for_tf_application_process_2019-20.pdf` <- `https://english.fas.harvard.edu/search?search=Course&page=2` -> `https://english.fas.harvard.edu/search?search=Course&page=2`
- `https://english.fas.harvard.edu/sites/g/files/omnuum1611/files/english/files/_course_listing_for_tf_application_process_2019-20_for_20-21_0_0.pdf` <- `https://english.fas.harvard.edu/search?search=Course&page=3` -> `https://english.fas.harvard.edu/search?search=Course&page=3`
- `https://english.fas.harvard.edu/sites/g/files/omnuum1611/files/english/files/_course_listing_for_tf_application_process_2019-20_for_20-21_revised_pdf.pdf` <- `https://english.fas.harvard.edu/search?search=Course&page=4` -> `https://english.fas.harvard.edu/search?search=Course&page=4`
- `https://english.fas.harvard.edu/sites/g/files/omnuum1611/files/english/files/an_invitation_to_a_christmas_game4.pdf` <- `https://english.fas.harvard.edu/search?page=96` -> `https://english.fas.harvard.edu/search?page=96`
- `https://english.fas.harvard.edu/sites/g/files/omnuum1611/files/english/files/border_crossing_fictions_andy_koenig.pdf` <- `https://english.fas.harvard.edu/search?search=Fiction&page=4` -> `https://english.fas.harvard.edu/search?search=Fiction&page=4`

### astronomy.fas.harvard.edu
**true_orphan:**
- `http://astronomy.fas.harvard.edu/sites/g/files/omnuum6286/files/astronomy/files/research_paper_oral_exam.pdf` <- `http://astronomy.fas.harvard.edu/search?search=2013&page=5` -> `https://astronomy.fas.harvard.edu/search?search=2013&page=5`
- `https://astronomy.fas.harvard.edu/sites/g/files/omnuum6286/files/astronomy/files/2020_2021_origins_undergraduate_term_prize_award_letter.docx` <- `https://astronomy.fas.harvard.edu/search?search=Undergraduate&page=2` -> `https://astronomy.fas.harvard.edu/search?search=Undergraduate&page=2`
- `https://astronomy.fas.harvard.edu/sites/g/files/omnuum6286/files/astronomy/files/barkana.pdf` <- `https://astronomy.fas.harvard.edu/search?search=February` -> `https://astronomy.fas.harvard.edu/search?search=February`
- `https://astronomy.fas.harvard.edu/sites/g/files/omnuum6286/files/astronomy/files/cfa_research_undergrad_2013.pdf` <- `https://astronomy.fas.harvard.edu/search?search=2013&page=1` -> `https://astronomy.fas.harvard.edu/search?search=2013&page=1`
- `https://astronomy.fas.harvard.edu/sites/g/files/omnuum6286/files/astronomy/files/cfa_research_undergrad_2015_1.pdf` <- `https://astronomy.fas.harvard.edu/search?search=2015` -> `https://astronomy.fas.harvard.edu/search?search=2015`
- `https://astronomy.fas.harvard.edu/sites/g/files/omnuum6286/files/astronomy/files/cfa_research_undergrad_2018.pdf` <- `https://astronomy.fas.harvard.edu/search?search=2018` -> `https://astronomy.fas.harvard.edu/search?search=2018`

### anthropology.fas.harvard.edu
**true_orphan:**
- `https://anthropology.fas.harvard.edu/sites/g/files/omnuum6776/files/10_18_24_anthropology_spring_2025_course_list.pdf` <- `https://anthropology.fas.harvard.edu/search?search=2025` -> `https://anthropology.fas.harvard.edu/search?search=2025`
- `https://anthropology.fas.harvard.edu/sites/g/files/omnuum6776/files/anthropology/files/advising_packet_2021_new_2.pdf` <- `https://anthropology.fas.harvard.edu/search?search=2021` -> `https://anthropology.fas.harvard.edu/search?search=2021`
- `https://anthropology.fas.harvard.edu/sites/g/files/omnuum6776/files/anthropology/files/anthro_fall_2023_course_list_july_11_update.pdf` <- `https://anthropology.fas.harvard.edu/search?search=Fall` -> `https://anthropology.fas.harvard.edu/search?search=Fall`
- `https://anthropology.fas.harvard.edu/sites/g/files/omnuum6776/files/anthropology/files/anthropology_course_list_fall_2024_4_5_24.pdf` <- `https://anthropology.fas.harvard.edu/search?search=2024&page=2` -> `https://anthropology.fas.harvard.edu/search?search=2024&page=2`
- `https://anthropology.fas.harvard.edu/sites/g/files/omnuum6776/files/anthropology/files/anthropology_cross-listed_courses_2023-24.pdf` <- `https://anthropology.fas.harvard.edu/search?search=2023&page=1` -> `https://anthropology.fas.harvard.edu/search?search=2023&page=1`
- `https://anthropology.fas.harvard.edu/sites/g/files/omnuum6776/files/anthropology/files/anthropology_cross-listed_courses_ay_21-22_0.pdf` <- `https://anthropology.fas.harvard.edu/search?search=2021&page=4` -> `https://anthropology.fas.harvard.edu/search?search=2021&page=4`

### ofa.fas.harvard.edu
**true_orphan:**
- `http://ofa.fas.harvard.edu/sites/g/files/omnuum4081/files/2025-06/Affiliated%20Box%20Office%20Requirements%20Form%20for%20Sanders%20Theatre%20events.pdf` <- `http://ofa.fas.harvard.edu/search?page=66` -> `https://ofa.fas.harvard.edu/search?page=66`
- `http://ofa.fas.harvard.edu/sites/g/files/omnuum4081/files/makeart/files/2011_fall_artofsurvival_program.pdf` <- `http://ofa.fas.harvard.edu/search?page=55` -> `https://ofa.fas.harvard.edu/search?page=55`
- `http://ofa.fas.harvard.edu/sites/g/files/omnuum4081/files/makeart/files/2012_spring_springperformances_program.pdf` <- `http://ofa.fas.harvard.edu/search?page=55` -> `https://ofa.fas.harvard.edu/search?page=55`
- `http://ofa.fas.harvard.edu/sites/g/files/omnuum4081/files/makeart/files/2014_fall_lookup_program.pdf` <- `http://ofa.fas.harvard.edu/search?page=55` -> `https://ofa.fas.harvard.edu/search?page=55`
- `http://ofa.fas.harvard.edu/sites/g/files/omnuum4081/files/makeart/files/2016_fall_wunder_program_copy.pdf` <- `http://ofa.fas.harvard.edu/search?page=54` -> `https://ofa.fas.harvard.edu/search?page=54`
- `http://ofa.fas.harvard.edu/sites/g/files/omnuum4081/files/makeart/files/2017_spring_five_pieces_program.pdf` <- `http://ofa.fas.harvard.edu/search?page=54` -> `https://ofa.fas.harvard.edu/search?page=54`

### dso.college.harvard.edu
**true_orphan:**
- `http://dso.college.harvard.edu/sites/g/files/omnuum7076/files/dso/files/2025_spring_firstyear_faculty_dinner_invitations.pdf` <- `http://dso.college.harvard.edu/search?page=10` -> `https://dso.college.harvard.edu/search?page=10`
- `http://dso.college.harvard.edu/sites/g/files/omnuum7076/files/dso/files/owc_job_description_class_of_2029.pdf` <- `http://dso.college.harvard.edu/search?page=10` -> `https://dso.college.harvard.edu/search?page=10`
- `https://dso.college.harvard.edu/sites/g/files/omnuum7076/files/dso/files/2019_harvard_yard_map.pdf` <- `https://dso.college.harvard.edu/search?search=Yards&page=13` -> `https://dso.college.harvard.edu/search?search=Yards&page=13`
- `https://dso.college.harvard.edu/sites/g/files/omnuum7076/files/dso/files/2022_fair_assignments.pdf` <- `https://dso.college.harvard.edu/search?page=43` -> `https://dso.college.harvard.edu/search?page=43`
- `https://dso.college.harvard.edu/sites/g/files/omnuum7076/files/dso/files/2022_student_organization_fair_brochure.pdf` <- `https://dso.college.harvard.edu/search?search=Student+Organizations+and+Resources&page=2` -> `https://dso.college.harvard.edu/search?search=Student+Organizations+and+Resources&page=2`
- `https://dso.college.harvard.edu/sites/g/files/omnuum7076/files/dso/files/2024_crimson_yard_welcome_letter_final.pdf` <- `https://dso.college.harvard.edu/search?search=Crimson+Yard` -> `https://dso.college.harvard.edu/search?search=Crimson+Yard`

