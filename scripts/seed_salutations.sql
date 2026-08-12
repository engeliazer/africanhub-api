-- Seed default salutations (idempotent — safe to run multiple times)
-- Run after salutations table exists

INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'CPA', 'cpa', 1, 1, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'cpa');

INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'CPA. Dr.', 'cpa_dr', 1, 2, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'cpa_dr');

INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'Dr.', 'dr', 0, 3, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'dr');

INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'Mr.', 'mr', 0, 4, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'mr');

INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'Ms.', 'ms', 0, 5, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'ms');

INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'Mrs.', 'mrs', 0, 6, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'mrs');

INSERT INTO salutations (label, code, qualifies_for_cpd, display_order, is_active)
SELECT 'None', 'none', 0, 7, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM salutations WHERE code = 'none');

SELECT id, label, qualifies_for_cpd, display_order
FROM salutations
ORDER BY display_order;
