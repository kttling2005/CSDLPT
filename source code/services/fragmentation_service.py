def get_site_by_region(region):

    region = region.lower()

    if "hà nội" in region:
        return "HN"

    elif "đà nẵng" in region:
        return "DN"

    elif "tphcm" in region or "hồ chí minh" in region:
        return "TPHCM"

    else:
        return None