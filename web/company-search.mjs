export function formatCompany(company) {
  return `${company.name} (${company.ticker})`;
}


export function rankCompanyMatches(companies, query, limit = 8) {
  const needle = query.trim().toLowerCase();
  if (!needle) return [];

  return companies
    .map((company, index) => {
      const ticker = company.ticker.toLowerCase();
      const name = company.name.toLowerCase();
      let rank = null;
      if (ticker === needle) rank = 0;
      else if (ticker.startsWith(needle)) rank = 1;
      else if (name.startsWith(needle)) rank = 2;
      else if (ticker.includes(needle)) rank = 3;
      else if (name.includes(needle)) rank = 4;
      return { company, index, rank };
    })
    .filter(({ rank }) => rank !== null)
    .sort((first, second) => first.rank - second.rank || first.index - second.index)
    .slice(0, limit)
    .map(({ company }) => company);
}


export function resolveCompanyTicker(inputValue, selectedCompany) {
  const value = inputValue.trim();
  if (selectedCompany && value === formatCompany(selectedCompany)) return selectedCompany.ticker;
  if (!/^[a-z0-9][a-z0-9.-]{0,9}$/i.test(value)) return null;
  return value.toUpperCase();
}


export function moveCompanySelection(activeIndex, key, resultCount) {
  if (!resultCount) return -1;
  if (key === 'ArrowDown') return (activeIndex + 1) % resultCount;
  if (key === 'ArrowUp') return (activeIndex - 1 + resultCount) % resultCount;
  return activeIndex;
}


export function fiscalYearChoices(currentYear) {
  const years = [];
  for (let year = currentYear + 1; year >= 2009; year -= 1) years.push(year);
  return years;
}
