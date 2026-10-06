patterns = [
    ('crowdstrike', 'CrowdStrike, Inc.'),
    ('corel', 'Corel'),
    ('apple', 'Apple Inc.'),
    ('realtek', 'Realtek Semiconductor Corp'),
    ('silicon laboratories', 'Silicon Laboratories'),
    ('google', 'Google'),
    ('anthropic', 'Anthropic'),
    ('dell', 'Dell'),
    ('lenovo', 'Lenovo'),
    ('intel', 'Intel Corporation'),
    ('advanced micro devices', 'Advanced Micro Devices, Inc. (AMD)'),
    ('amd', 'Advanced Micro Devices, Inc. (AMD)'),
    ('nvidia', 'NVIDIA Corporation'),
    ('riot', 'Riot Games, Inc.'),
    ('kitware', 'Kitware, Inc.'),
    ('oracle', 'Oracle Corporation'),
    ('warp', 'Warp, Inc.'),
    ('avast', 'Gen Digital Inc. / Avast'),
    ('mcafee', 'McAfee, LLC'),
    ('tlauncher', 'TLauncher'),
    ('wondershare', 'Wondershare Technology Co., Ltd.'),
    ('telegram', 'Telegram Messenger LLP'),
    ('kankaria', 'Kankaria'),
    ('adobe', 'Adobe Inc.'),
    ('mozilla', 'Mozilla'),
    ('opera', 'Opera Software'),
    ('vivaldi', 'Vivaldi Technologies'),
    ('cisco', 'Cisco Systems, Inc.'),
    ('fortinet', 'Fortinet, Inc.'),
    ('document foundation', 'The Document Foundation'),
    ('libreoffice', 'The Document Foundation'),
    ('filezilla', 'FileZilla Project'),
    ('eclipse', 'Eclipse Foundation'),
    ('postgresql', 'PostgreSQL Global Development Group'),
    ('red hat', 'Red Hat, Inc.'),
    ('redhat', 'Red Hat, Inc.'),
    ('splunk', 'Splunk, Inc.'),
    ('foundry', 'The Foundry'),
    ('steelseries', 'SteelSeries'),
    ('lists.ubuntu.com', 'Ubuntu Community'),
    ('ubuntu developers', 'Ubuntu Community'),
    ('canonical.com', 'Canonical'),
    ('canonical', 'Canonical'),
    ('debian.org', 'Debian Project'),
    ('debian qa', 'Debian Project'),
    ('gnu.org', 'Free Software Foundation'),
    ('free software foundation', 'Free Software Foundation'),
]

conflicts = []
for p1, v1 in patterns:
    for p2, v2 in patterns:
        if p1 != p2 and p1 in p2:
            if v1 != v2:
                conflicts.append((p1, v1, p2, v2))
            else:
                print(f'Subpattern with SAME vendor: "{p1}" in "{p2}" -> {v1}')

print('Conflicts with DIFFERENT vendors:', conflicts)
