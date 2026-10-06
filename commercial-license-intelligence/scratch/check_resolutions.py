# Detailed analysis of 42 Custom compare values apps

custom_resolutions = {
    # 1. Explicit CAL in name
    251466: ("CAL", "Product name explicitly specifies '9.0 CAL'"), # IBM Domino Messaging 9.0 CAL
    
    # 2. Explicit User in name or Oracle/PeopleSoft user-based applications
    70891: ("Users", "Product name explicitly specifies 'Employee User'"), # Oracle Access Management Employee User
    13960: ("Users", "PeopleSoft Payroll is licensed per Employee / User (PreferredMetric=9 in SRS)"), # Peoplesoft Enterprise Payroll
    403492: ("Users", "PeopleSoft HR is licensed per Employee / User (PreferredMetric=9 in SRS)"), # PeopleSoft Enterprise Human Resources
    111391: ("Users", "Oracle GRC Advanced Controls licensed per Application User (PreferredMetric=9 in SRS)"), # Oracle EBS (GRC) Advanced Controls
    500427: ("Users", "Oracle Services Procurement licensed per User (PreferredMetric=9 in SRS)"), # Oracle EBS Purchasing - Option: Services Procurement
    301738: ("Users", "PeopleSoft Time and Labor licensed per Employee / User"), # PeopleSoft Enterprise Time and Labor 9
    349780: ("Users", "PeopleSoft eRecruit licensed per Employee / User"), # PeopleSoft Enterprise eRecruit
    575883: ("Users", "PeopleSoft ePerformance licensed per Employee / User"), # PeopleSoft Enterprise ePerformance 9
    600425: ("Users", "PeopleSoft Learning Management licensed per Trainee / User"), # PeopleSoft Enterprise Learning Management
    59822: ("Users", "PeopleSoft HCM Portal Pack licensed per Employee / User"), # PeopleSoft Enterprise HCM Portal Pack
    361180: ("Users", "IBM Connections Cloud S1 is a SaaS collaboration suite licensed per User"), # IBM Connections Cloud S1
    623575: ("Users", "Oracle Internet Developer Suite licensed per Named User Plus"), # Oracle Internet Developer Suite
    6366: ("Users", "Oracle Hyperion Planning Plus licensed per Application User"), # Oracle Hyperion Planning Plus
    832793: ("Users", "Oracle EBS Incentive Compensation licensed per Application User / Monitored User"), # Oracle EBS Incentive Compensation
    92753: ("Users", "Oracle Inventory Management 12 licensed per Application User"), # Oracle Inventory Management 12
    115997: ("Users", "Oracle Financials 12 licensed per Application User"), # Oracle Financials 12
    361040: ("Users", "Oracle Internet Expenses 12 licensed per Application User"), # Oracle Internet Expenses 12
    533161: ("Users", "Oracle Procurement Contracts for Oracle Purchasing 12 licensed per Application User"), # Oracle Procurement Contracts
    572926: ("Users", "Oracle Purchasing 12 licensed per Application User"), # Oracle Purchasing 12
    853354: ("Users", "Oracle iSupplier Portal for Oracle Purchasing 12 licensed per Application User"), # Oracle iSupplier Portal
    860886: ("Users", "Oracle iProcurement 12 licensed per Application User"), # Oracle iProcurement 12

    # 3. Server / Endpoint / Installations
    681724: ("Installations", "NetBackup NDMP Option Server is licensed per Server/Install (PreferredMetric=1 in SRS)"), # Symantec NetBackup 7.6 NDMP
    732596: ("Installations", "NetBackup NDMP Option Server is licensed per Server/Install (PreferredMetric=1 in SRS)"), # VERITAS NetBackup 8.0 NDMP
    95588: ("Installations", "IBM Rational Functional Tester client tool (SRS PreferredMetric=1, 27/28 rows Installation)"), # IBM Rational Functional Tester 9.1
    572559: ("Installations", "IBM Rational Performance Tester client tool (SRS PreferredMetric=1, 39/40 rows Installation)"), # IBM Rational Performance Tester 9.2
    836256: ("Installations", "IBM Rational Application Developer desktop IDE (SRS PreferredMetric=1)"), # IBM Rational Application Developer 9.7
    349709: ("Installations", "IBM Aspera High-Speed Transfer Endpoint is licensed per Endpoint/Install"), # IBM Aspera High-Speed Transfer Endpoint 3.8
    293033: ("Devices", "IBM Endpoint Manager (BigFix) for Lifecycle Management is licensed per Managed Client Device"), # IBM Endpoint Manager 9.1

    # 4. Applications where metric cannot be determined with certainty -> leave blank per Rule 5
    54185: ("", "IBM Security Identity and Access Manager uses RVU/PVU or User depending on deployment"), # IBM Security Identity and Access Manager 3.1
    70947: ("", "IBM Security Identity Manager Host Edition uses RVU or Install depending on tier"), # IBM Security Identity Manager 7.0 Host Edition
    730401: ("", "IBM Security Identity Manager Host Edition uses RVU or Install depending on tier"), # IBM Security Identity Manager 6.0 Host Edition
    113418: ("", "IBM Security Access Manager Virtual Federation Edition metric varies by virtual instance / user"), # IBM Security Access Manager Virtual Federation Edition
    227548: ("", "IBM Security Access Manager Virtual Edition metric varies by virtual instance / user"), # IBM Security Access Manager 9.0 Virtual Edition
    526372: ("", "IBM Security Access Manager for Web metric varies by user / server"), # IBM Security Access Manager for Web 7.0
    436818: ("", "IBM Rational Performance Test Pack metric varies by virtual testers / protocol"), # IBM Rational Performance Test Pack
    422456: ("", "AppDynamics Pro Java licensed by JVM instance, host or CPU core"), # AppDynamics Pro Java
    544943: ("", "Oracle BI Publisher licensed per Named User Plus or Processor Cores"), # Oracle Business Intelligence Publisher 12
    663692: ("", "IBM Tivoli Application Dependency Discovery Manager uses RVU or Managed Server"), # IBM Tivoli Application Dependency Discovery Manager 7.3
    689433: ("", "Adobe Experience Manager licensed by instance or media library volume"), # Adobe Experience Manager 6.0
    759126: ("", "Oracle Policy Modeling metric varies"), # Oracle Policy Modeling 10.4
    906799: ("", "Adobe Target Standard licensed by web traffic / pageviews") # Adobe Target Standard
}

print(f"Total mapped: {len(custom_resolutions)}")
resolved = sum(1 for v in custom_resolutions.values() if v[0] != "")
blank = sum(1 for v in custom_resolutions.values() if v[0] == "")
print(f"Resolved: {resolved}, Blank (unresolved): {blank}")
