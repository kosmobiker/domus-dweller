{% macro extract_district(district_col, location_approx_col, title_col) %}
COALESCE(
    CASE 
        WHEN {{ district_col }} IS NOT NULL AND {{ district_col }} != 'Kraków' AND TRIM({{ district_col }}) != '' 
        THEN {{ district_col }}
        ELSE NULL
    END,
    CASE
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])pr[aą]dnik(?:u|a|iem)?\s+czerwon(?:y|ym|ego)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Prądnik Czerwony'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])pr[aą]dnik(?:u|a|iem)?\s+bia[lł](?:y|ym|ego)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Prądnik Biały'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])podg[oó]rz(?:e|u|a|em)\s+duchack(?:ie|im|iego)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Podgórze Duchackie'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])wol[aię]?\s+duchack[a-ząćęłńóśźż]*(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Podgórze Duchackie'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])piask(?:i|ach)\s+now(?:e|ych)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Podgórze Duchackie'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])kurdwan[oó]w(?:ie|a)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Podgórze Duchackie'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])star(?:e|ego|ym|emu)\s+(?:miast(?:o|a|u|em)|mie[sś]cie)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Stare Miasto'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])kleparz(?:u|a)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Stare Miasto'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])kazimierz(?:u|a)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Stare Miasto'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])[lł]agiewnik(?:i|ach|ami|om)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Łagiewniki-Borek Fałęcki'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])(?:borek|borku|borka)\s+fa[lł][eę]ck(?:i|im|iego)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Łagiewniki-Borek Fałęcki'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])bie[zż]an[oó]w(?:ie)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Bieżanów-Prokocim'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])prokocim(?:iu|ia|iem)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Bieżanów-Prokocim'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])koz[lł][oó]w(?:ek|ku)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Bieżanów-Prokocim'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])wzg[oó]rz(?:a|ach|om|ami)?\s+krzes[lł]awick(?:ie|ich|im)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Wzgórza Krzesławickie'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])now(?:a|ej|ą)\s+hu(?:ta|cie|tę|ty)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Nowa Huta'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])(?:star[aej]\s+)?krowodrz(?:a|y|ę|ą)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Krowodrza'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])[lł]obz[oó]w(?:ie)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Krowodrza'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])bronowic(?:e|ach|ami|om)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Bronowice'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])zwierzyn(?:iec|cu|ca|cem)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Zwierzyniec'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])wol[aię]?\s+justowsk[a-ząćęłńóśźż]*(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Zwierzyniec'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])salwator(?:ze|a)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Zwierzyniec'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])d[eę]bnik(?:i|ach|ami|om)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Dębniki'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])ruczaj(?:u|em)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Dębniki'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])podwawelskie(?:go|mu)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Dębniki'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])(?:star(?:e|ym)\s+)?podg[oó]rz(?:e|u|a|em)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Podgórze'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])zab[lł]oci(?:e|u|a)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Podgórze'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])czy[zż]yn(?:y|ach|ami|om)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Czyżyny'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])mistrzejowic(?:e|ach|ami|om)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Mistrzejowice'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])os(?:\.|\s+iedle)?\s+piast[oó]w(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Mistrzejowice'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])bie[nń]czyc(?:e|ach|ami|om)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Bieńczyce'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])swoszowic(?:e|ach|ami|om)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Swoszowice'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])grzeg[oó]rz(?:ki|kach|kami|ek|kom)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Grzegórzki'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])wieliczk(?:a|i|ce|ą)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Wieliczka'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])skawin(?:a|y|ie|ą)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Skawina'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])niepo[lł]omic(?:e|ach|ami|om)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Niepołomice'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])zabierz[oó]w(?:ie)?(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Zabierzów'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])zielonk(?:i|ach|ami|om)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Zielonki'
        WHEN regexp_matches(COALESCE({{ location_approx_col }} || ' ', '') || COALESCE({{ title_col }}, ''), '(?i)(?:^|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])[sś]wi[aą]tnik(?:i|ach)?\s+g[oó]rn(?:e|ych)(?:$|[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ])') THEN 'Świątniki Górne'
        ELSE NULL
    END,
    {{ district_col }}
)
{% endmacro %}
