# -*- coding: utf-8 -*-
import glob, re, subprocess

print("=== FULL 19-CHAPTER AUDIT ===")

chapters = [f"chapter_{i}.md" for i in range(1, 20)]

earth_terms = [
    r'\bбогемск', r'\bвенецианск', r'\bкаррарск', r'\bкоринфск',
    r'\bантоновск', r'\bГраал', r'\bГавриил\b', r'\bИзели\b'
]

modern_jargon = [
    r'\bстереоскоп', r'\bгироскоп', r'\bэллипсоид', r'\bпетрикор',
    r'\bгеосмин', r'\bбарометрич', r'\bэндолимф'
]

total_words = 0
all_passed = True

for ch in chapters:
    with open(ch, 'r', encoding='utf-8') as f:
        text = f.read()
    
    words = len(re.findall(r'\b\w+\b', text))
    total_words += words
    
    # Check semicolons
    semicolons = text.count(';')
    
    # Check forbidden contrasts
    contrasts = len(re.findall(r'\bне\s+[^,\.!?]{2,40},\s*а\s+[^,\.!?]{2,40}\b', text, re.I))
    
    # Check earth terms
    found_earth = []
    for pat in earth_terms:
        m = re.findall(pat, text, re.I)
        if m:
            found_earth.extend(m)
            
    # Check jargon
    found_jargon = []
    for pat in modern_jargon:
        m = re.findall(pat, text, re.I)
        if m:
            found_jargon.extend(m)
            
    # Check яростн
    found_yarost = len(re.findall(r'\bяростн', text, re.I))
    
    status = "OK"
    issues = []
    if not (3000 <= words <= 3300):
        status = "WARN"
        issues.append(f"words={words}")
    if semicolons > 0:
        status = "FAIL"
        issues.append(f";={semicolons}")
    if contrasts > 0:
        status = "FAIL"
        issues.append(f"contrasts={contrasts}")
    if found_earth:
        status = "FAIL"
        issues.append(f"earth={found_earth}")
    if found_jargon:
        status = "FAIL"
        issues.append(f"jargon={found_jargon}")
    if found_yarost > 0:
        status = "FAIL"
        issues.append(f"яростн={found_yarost}")
        
    issue_str = f" [{', '.join(issues)}]" if issues else ""
    print(f"{ch:15} | words: {words:4} | {status}{issue_str}")
    if status == "FAIL":
        all_passed = False

print("-" * 50)
print(f"TOTAL WORDS ACROSS 19 CHAPTERS: {total_words}")
print(f"ALL STRICT CHECKS PASSED: {all_passed}")
