-- Chinook query activity (week 3, Thursday). Write one query under each question.
-- How to run this file, what the tables are and what each question expects is in
-- README.md beside it. Test each query at the mysql> prompt first, then paste it here.
-- Hand-in: week-03/hackathon/chinook/chinook-questions.sql in your own learner repo.

USE Chinook;


-- ============================================================
-- Part A: one table (SELECT, WHERE, ORDER BY, LIMIT)
-- ============================================================

-- Q01. Every genre name, A to Z.


-- Q02. The customers who live in Canada: first name, last name and city, sorted by city.


-- Q03. The ten longest tracks that run over 10 minutes: name and length in minutes
--      (one decimal), longest first.


-- Q04. Invoices from 2025 whose total is above 10: invoice id, date and total, highest total first.


-- Q05. Albums whose title contains the word Live, A to Z.


-- Q06. Customers in the USA or Canada who gave a company name: the full name in one
--      column called customer, the company and the country, sorted by company.


-- ============================================================
-- Part B: aggregates (GROUP BY, HAVING)
-- ============================================================

-- Q07. One row about the whole Track table: how many tracks, and the shortest, longest
--      and average length in minutes (two decimals).


-- Q08. How many customers live in each country, most customers first, then country A to Z.


-- Q09. Total billed per billing country (two decimals), only the countries billed more
--      than 100 in all, highest first.


-- Q10. Albums with more than 25 tracks: the album id and its track count, most tracks first.
--      (Only the id for now. Q13 adds the title.)


-- Q11. Per customer id: how many invoices and how much they spent in all (two decimals),
--      only the customers who spent more than 45, biggest spender first.


-- ============================================================
-- Part C: joins
-- ============================================================

-- Q12. Every album title with the name of its artist, sorted by artist then title.


-- Q13. Q10 again, with the album title and the artist name instead of the id.


-- Q14. Every track by Iron Maiden: album title and track name, sorted by album then track.


-- Q15. Every Jazz track: track name, album title and media type name, sorted by album then track.


-- Q16. Each customer with the employee who supports them: customer full name and rep full
--      name (one column each), sorted by rep then customer.


-- Q17. Every employee and how many customers they support, including the employees who
--      support nobody (they show 0), most customers first, then last name.


-- Q18. The five genres that earned the most: genre name and revenue (the sum of unit price
--      times quantity over every invoice line, two decimals), highest first.


-- Q19. How many tracks have never been sold? One number, found with a LEFT JOIN
--      from Track to InvoiceLine and a test for NULL.


-- ============================================================
-- Part D: subqueries
-- ============================================================

-- Q20. Every track on the album called Let There Be Rock: name and length in milliseconds,
--      in track order (by TrackId). Use a subquery for the album id, not a join.


-- Q21. Tracks that cost more than the average track price: name and unit price,
--      the first ten alphabetically.


-- Q22. Artists with no album at all, A to Z. Write it with NOT IN and a subquery.


-- Q22b. Same question, written as a LEFT JOIN. Same rows?


-- Q23. The invoice with the highest total: invoice id, customer id, date and total.


-- Q24. Customers who bought at least one Metal track: full name and country, sorted by
--      name. The list of customer ids comes from a subquery that joins Invoice,
--      InvoiceLine, Track and Genre.


-- ============================================================
-- Stretch (for home, or if you finish early)
-- ============================================================

-- Q25. Each employee with the name of the person they report to. The general manager
--      reports to nobody and must still appear, with NULL. Hint: join Employee to
--      itself under two aliases.


-- Q26. Customers whose total spend is above the average customer's total spend: full name
--      and what they spent (two decimals), biggest first. The average of the per-customer
--      totals needs a subquery in FROM (the notes page calls it a derived table).

