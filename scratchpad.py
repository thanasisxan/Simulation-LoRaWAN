from jenkspy import JenksNaturalBreaks

# toas = [1320, 1100, 970, 560, 465, 346, 654, 376, 120, 40, 50, 60, 44, 66, 77, 88, 433, 768, 123, 522,
#         80, 87, 56, 87]

toas = [174.3361, 174.3362, 174.3363, 553.9844, 553.9845, 553.9846, 1215.9367, 1026.0488, 174.3369, 553.9848, 307.7127, 1940.352,
        174.3369, 553.9845, 307.7124]

# toas.sort()

jnb = JenksNaturalBreaks(8)

jnb.fit(toas)
try:
    # print(jnb.labels_)
    print(jnb.groups_)
    # print(jnb.inner_breaks_)
except:
    pass

i = 0
for g in jnb.groups_:
    print("\nGroup ", i, ":", g)
    print("Total duration:", sum(g), "ms")
    i += 1
