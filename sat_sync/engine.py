class ReconciliationEngine:

    def __init__(self, rules):
        self.rules = rules

    def run(self, identities):

        findings = []

        for rule in self.rules:
            findings.extend(rule.evaluate(identities))

        return findings
        
