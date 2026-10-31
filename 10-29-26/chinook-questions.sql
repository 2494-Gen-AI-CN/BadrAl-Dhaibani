-- Active: 1793208395994@@127.0.0.1@3306@Chinook
-- Chinook query activity (week 3, Thursday). Write one query under each question.
-- How to run this file, what the tables are and what each question expects is in
-- README.md beside it. Test each query at the mysql> prompt first, then paste it here.
-- Hand-in: week-03/hackathon/chinook/chinook-questions.sql in your own learner repo.

USE Chinook;

-- ============================================================
-- Part A: one table (SELECT, WHERE, ORDER BY, LIMIT)
-- ============================================================

-- Q01. Every genre name, A to Z.
SELECT name
FROM Genre
ORDER BY name ASC

-- Q02. The customers who live in Canada: first name, last name and city, sorted by city.
SELECT FirstName, LastName, City
FROM Customer
WHERE Country = 'Canada'
ORDER BY City ASC

-- Q03. The ten longest tracks that run over 10 minutes: name and length in minutes
--      (one decimal), longest first.
SELECT Name, ROUND(Milliseconds/60000, 1) AS minutes
FROM Track
WHERE ROUND(Milliseconds/60000, 1) > 10
ORDER BY minutes DESC
LIMIT 10;

-- Q04. Invoices from 2025 whose total is above 10: invoice id, date and total, highest total first.
SELECT InvoiceId, InvoiceDate, Total
FROM Invoice
WHERE YEAR(InvoiceDate) = 2025 AND Total > 10
ORDER BY Total DESC;

-- Q05. Albums whose title contains the word Live, A to Z.
SELECT Title
FROM Album
WHERE Title LIKE '%live%'
ORDER BY Title ASC;

-- Q06. Customers in the USA or Canada who gave a company name: the full name in one
--      column called customer, the company and the country, sorted by company.
SELECT CONCAT(FirstName, ' ', LastName) AS customer, Company, Country
FROM Customer
WHERE (Country = 'USA' OR Country = 'Canada') AND Company IS NOT NULL
ORDER BY Company DESC;

-- ============================================================
-- Part B: aggregates (GROUP BY, HAVING)
-- ============================================================

-- Q07. One row about the whole Track table: how many tracks, and the shortest, longest
--      and average length in minutes (two decimals).
SELECT 
    COUNT(*) AS tracks,
    ROUND(MIN(Milliseconds) / 60000, 2) AS shortest,
    ROUND(MAX(Milliseconds) / 60000, 2) AS longest,
    ROUND(AVG(Milliseconds) / 60000, 2) AS average
FROM Track

-- Q08. How many customers live in each country, most customers first, then country A to Z.
SELECT COUNT(*) AS customers, Country
FROM Customer
GROUP BY Country
ORDER BY
    customers DESC,
    Country ASC

-- Q09. Total billed per billing country (two decimals), only the countries billed more
--      than 100 in all, highest first.
SELECT SUM(Total) AS total_billed, BillingCountry
FROM Invoice
GROUP BY BillingCountry
HAVING SUM(Total) > 100
ORDER BY total_billed DESC

-- Q10. Albums with more than 25 tracks: the album id and its track count, most tracks first.
--      (Only the id for now. Q13 adds the title.)
SELECT a.AlbumId, COUNT(*) AS track_count
FROM Album AS a
JOIN Track AS t
ON t.AlbumId = a.AlbumId
GROUP BY a.AlbumId
HAVING COUNT(*) > 25
ORDER BY track_count DESC;

-- Q11. Per customer id: how many invoices and how much they spent in all (two decimals),
--      only the customers who spent more than 45, biggest spender first. 
SELECT c.CustomerId, COUNT(*) AS invoice_count, SUM(i.Total) AS invoice_total
FROM Customer AS c
JOIN Invoice AS i ON i.CustomerId = c.CustomerId
GROUP BY c.CustomerId
HAVING SUM(i.Total) > 45
ORDER BY invoice_total DESC;

-- ============================================================
-- Part C: joins
-- ============================================================

-- Q12. Every album title with the name of its artist, sorted by artist then title.
SELECT al.Title, ar.Name
FROM Album AS al
JOIN Artist AS ar ON ar.ArtistId = al.ArtistId
ORDER BY
    ar.Name ASC,
    al.Title ASC;

-- Q13. Q10 again, with the album title and the artist name instead of the id.
SELECT al.Title, ar.Name, COUNT(*) AS track_count
FROM Album AS al
JOIN Track AS t ON al.AlbumId = t.AlbumId
JOIN Artist AS ar ON al.ArtistId = ar.ArtistId
GROUP BY al.AlbumId
HAVING COUNT(*) > 25
ORDER BY track_count DESC;

-- Q14. Every track by Iron Maiden: album title and track name, sorted by album then track.
SELECT al.Title, t.Name
FROM Artist AS a
JOIN Album AS al ON a.ArtistId = al.ArtistId
JOIN Track AS t ON al.AlbumId = t.AlbumId
WHERE a.Name = 'Iron Maiden'
ORDER BY
    al.Title ASC,
    t.Name ASC;

-- Q15. Every Jazz track: track name, album title and media type name, sorted by album then track.
SELECT t.Name, al.Title, m.Name
FROM Genre AS g
JOIN Track AS t ON g.GenreId = t.GenreId
JOIN Album AS al ON t.AlbumId = al.AlbumId
JOIN MediaType AS m ON t.MediaTypeId = m.MediaTypeId
WHERE g.Name = 'Jazz'
ORDER BY
    al.Title ASC,
    t.Name ASC;

-- Q16. Each customer with the employee who supports them: customer full name and rep full
--      name (one column each), sorted by rep then customer.
SELECT CONCAT(c.FirstName, ' ', c.LastName) AS customer_name, CONCAT(e.FirstName, ' ', e.LastName) AS employee_name
FROM Customer AS c
JOIN Employee AS e ON c.SupportRepId = e.EmployeeId
ORDER BY
    employee_name ASC,
    customer_name ASC;

-- Q17. Every employee and how many customers they support, including the employees who
--      support nobody (they show 0), most customers first, then last name.
SELECT COUNT(c.CustomerId) AS customers_supporting, e.LastName
FROM Employee AS e
LEFT JOIN Customer AS c ON e.EmployeeId = c.SupportRepId
GROUP BY e.EmployeeId, e.LastName
ORDER BY customers_supporting DESC

-- Q18. The five genres that earned the most: genre name and revenue (the sum of unit price
--      times quantity over every invoice line, two decimals), highest first.
SELECT g.Name, ROUND(SUM(i.UnitPrice * i.Quantity), 2) AS revenue
FROM Genre AS g
JOIN Track AS t ON g.GenreId = t.GenreId
JOIN InvoiceLine AS i ON t.TrackId = i.TrackId
GROUP BY g.Name
ORDER BY revenue DESC
LIMIT 5;


-- Q19. How many tracks have never been sold? One number, found with a LEFT JOIN
--      from Track to InvoiceLine and a test for NULL.
SELECT COUNT(*)
FROM Track AS t
LEFT JOIN InvoiceLine AS i ON t.TrackId = i.TrackId
WHERE i.TrackId IS NULL;


-- ============================================================
-- Part D: subqueries
-- ============================================================

-- Q20. Every track on the album called Let There Be Rock: name and length in milliseconds,
--      in track order (by TrackId). Use a subquery for the album id, not a join.
SELECT t.Name, t.Milliseconds
FROM Track AS t
WHERE t.AlbumId = (
    SELECT al.AlbumId
    FROM Album AS al
    WHERE al.Title = 'Let There Be Rock'
)
ORDER BY t.TrackId;

-- Q21. Tracks that cost more than the average track price: name and unit price,
--      the first ten alphabetically.
SELECT t.Name, t.UnitPrice
FROM Track AS t
WHERE t.UnitPrice > (
    SELECT AVG(UnitPrice)
    FROM Track
)
ORDER BY t.Name
LIMIT 10;


-- Q22. Artists with no album at all, A to Z. Write it with NOT IN and a subquery.
SELECT a.Name
FROM Artist AS a
WHERE a.ArtistId NOT IN (
    SELECT ArtistId
    FROM Album
)
ORDER BY a.Name;

-- Q22b. Same question, written as a LEFT JOIN. Same rows?
SELECT ar.Name
FROM Artist AS ar
LEFT JOIN Album AS al ON ar.ArtistId = al.ArtistId
WHERE al.ArtistId IS NULL
ORDER BY ar.Name;

-- Q23. The invoice with the highest total: invoice id, customer id, date and total.
SELECT InvoiceId, CustomerId, InvoiceDate, Total
FROM Invoice
WHERE Total = (
    SELECT MAX(Total)
    FROM Invoice
);

-- Q24. Customers who bought at least one Metal track: full name and country, sorted by
--      name. The list of customer ids comes from a subquery that joins Invoice,
--      InvoiceLine, Track and Genre.
SELECT CONCAT(FirstName, ' ', LastName) AS fullname, Country
FROM Customer
WHERE CustomerId IN (
    SELECT i.CustomerId
    FROM Invoice AS i
    JOIN InvoiceLine AS il ON i.InvoiceId = il.InvoiceId
    JOIN Track AS t ON il.TrackId = t.TrackId
    JOIN Genre AS g ON t.GenreId = g.GenreId
    WHERE g.Name = 'Metal'
)
ORDER BY fullname;

-- ============================================================
-- Stretch (for home, or if you finish early)
-- ============================================================

-- Q25. Each employee with the name of the person they report to. The general manager
--      reports to nobody and must still appear, with NULL. Hint: join Employee to
--      itself under two aliases.
SELECT CONCAT(e.FirstName, ' ', e.LastName) AS employee, CONCAT(m.FirstName, ' ', m.LastName) AS manager
FROM Employee AS e
LEFT JOIN Employee AS m ON e.ReportsTo = m.EmployeeId;


-- Q26. Customers whose total spend is above the average customer's total spend: full name
--      and what they spent (two decimals), biggest first. The average of the per-customer
--      totals needs a subquery in FROM (the notes page calls it a derived table).

WITH result AS (
    SELECT CustomerId, SUM(Total) AS total
    FROM Invoice
    GROUP BY CustomerId
)
SELECT CONCAT(c.FirstName, ' ', c.LastName) AS full_name, ROUND(r.total, 2) AS total
FROM result AS r
JOIN Customer AS c ON r.CustomerId = c.CustomerId
WHERE r.total > (
    SELECT AVG(total)
    FROM result
)
ORDER BY r.total DESC;


