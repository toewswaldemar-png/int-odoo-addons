
RDB$PROCEDURE_NAME                                                                            RDB$PROCEDURE_SOURCE 
=============================================================================== ==================== 
P_8DAMPEL                                                                                                1a:2d1 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   DECLARE VARIABLE GEDRUCKT VARCHAR(1); DECLARE VARIABLE STCK INTEGER; DECLARE VARIABLE GELIEFERT INTEGER;  DECLARE VARIABLE BERICHT VARCHAR(1);  BEGIN  STATUS = 3;  SELECT GEDRUCKT FROM BELEG WHERE OID = :AOID INTO :GEDRUCKT;  IF (:GEDRUCKT = 'T') THEN  BEGIN  STATUS = 2;   SELECT FIRST 1 STCK, GELIEFERT, ABNR FROM BELEGPOS WHERE SOID = :AOID INTO :STCK, :GELIEFERT, :BERICHT;  IF ( (:BERICHT = 'T' ) AND (:STCK = :GELIEFERT) ) THEN  STATUS = 1;  END  SUSPEND; END
==============================================================================
P_ADRESSEOPSTAND                                                                                           1a:1 
==============================================================================
RDB$PROCEDURE_SOURCE:  
                       
BEGIN
  SELECT SUM(OFFEN) FROM BELEG
  WHERE BELEGART = 103
  AND ADROID = :AOID
  INTO :OP;
  SUSPEND;
END
==============================================================================
P_ADRESSEUMSATZ                                                                                           1a:f2 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN UPDATE ADRESSEN SET UMSATZ = ( SELECT SUM(NETTO) FROM beleg  WHERE BELEGART = 103 AND ADROID = :AOID ), OPSTAND = ( SELECT SUM(OFFEN) FROM BELEG WHERE BELEGART = 103 AND ADROID = :AOID ),  UMSATZJAHR = ( SELECT SUM(NETTO) FROM BELEG WHERE BELEGART = 103 AND ADROID = :AOID AND SUBSTR(BELEGDATUM,8,11) =  SUBSTR(CAST("today" as date),8,11))  WHERE ADRESSEN.OID = :AOID; SUSPEND; END
==============================================================================
P_ARTDIREKTSTATUS                                                                                        1a:2d7 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  DECLARE VARIABLE SPERRE VARCHAR(1); DECLARE VARIABLE DIREKT1 INTEGER; DECLARE VARIABLE DIREKT2 INTEGER;  BEGIN  STATUS = -1;  SELECT DIREKTLIEFERANT1, DIREKTLIEFERANT2, SPERRE FROM ARTIKEL WHERE OID = :AOID INTO :DIREKT1, :DIREKT2, :SPERRE;  IF (:SPERRE = 'T') THEN  STATUS = 0; ELSE BEGIN  IF (:DIREKT1 > 0) THEN STATUS = 1; ELSE STATUS = 0;  IF (:STATUS  = 0) THEN BEGIN IF (:DIREKT2 > 0) THEN STATUS = 1;  END  END SUSPEND; END
==============================================================================
P_ARTIKELGRUPPE                                                                                          1a:1de 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   BEGIN  SELECT BEZEICHNUNG FROM ARTIKELGRUPPEN WHERE OID = :AOID INTO :BEZEICHNUNG;  SUSPEND; END
==============================================================================
P_ARTOIDBG                                                                                               1a:d22 
==============================================================================
RDB$PROCEDURE_SOURCE:  
      BEGIN  BEGIN  FOR Select SOID, ASOID, ARTOID from Stuecklistenartikel where SOID = :ASTOID  Into :ASOID, :AASOID, :AARTOID DO BEGIN SUSPEND;  IF (AASOID >0 ) THEN  BEGIN  FOR Select * from P_ARTOIDBG(:AASOID) into :ASOID, :AASOID, :AARTOID DO  SUSPEND; END  END    END  END
==============================================================================
P_BEDARF                                                                                                1a:3720 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  DECLARE VARIABLE ZUB NUMERIC (15,2); DECLARE VARIABLE ABB NUMERIC (15,2); 

 DECLARE VARIABLE BST NUMERIC (15,2); 

 BEGIN  select sum(stck)-sum(geliefert) from belegpos p, beleg b where b.belegart = 105 and b.oid = p.soid 

  and b.abgeschlossen <> 'T' and artoid = :AOID INTO :ZUB; 

 IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB; 

 select sum(sollmenge-buchmenge) from prodartikel A, Produktion P where  P.oid = A.soid and p.status <> -1 and A.artoid = :AOID INTO :ABB; 

 IF (:ABB IS NULL) THEN ABB = 0; ELSE ABB = :ABB; select Bestand from P_BestandV(:AOID) INTO :BST;  

 IF (:BST IS NULL) THEN BST = 0; ELSE BST = :BST;  BEDARF = ZUB + BST - ABB; SUSPEND; END
==============================================================================
P_BELEGART                                                                                                 1a:d 
==============================================================================
RDB$PROCEDURE_SOURCE:  
 
BEGIN
  SELECT BELEGART FROM BELEG
  WHERE OID = :AOID
  INTO :BELEGART;
  SUSPEND;
END
==============================================================================
P_BELEGOFFEN                                                                                              1a:fb 
==============================================================================
RDB$PROCEDURE_SOURCE:  
           

DECLARE VARIABLE BETRAG NUMERIC(15, 2);
DECLARE VARIABLE SKONTO NUMERIC(15, 2);
DECLARE VARIABLE NACHLASS NUMERIC(15, 2);
                                     
BEGIN
  SELECT SUM(Betrag) FROM Zahlungen
  WHERE soid = :aoid
  INTO :BETRAG; 
  SELECT SUM(Skonto) FROM Zahlungen
  WHERE soid = :aoid
  INTO :SKONTO; 
  SELECT SUM(Nachlass) FROM Zahlungen
  WHERE soid = :aoid
  INTO :NACHLASS; 

  IF (:BETRAG IS NULL) THEN BETRAG = 0; ELSE BETRAG = :BETRAG;  
  IF (:NACHLASS IS NULL) THEN NACHLASS = 0; ELSE NACHLASS = :NACHLASS;  
  IF (:SKONTO IS NULL) THEN SKONTO = 0; ELSE SKONTO = :SKONTO;

  ZAHLUNG = SKONTO + NACHLASS + BETRAG;
  SUSPEND;
END
==============================================================================
P_BESTAND                                                                                                1a:1e1 
==============================================================================
RDB$PROCEDURE_SOURCE:  
                       

DECLARE VARIABLE ZUB NUMERIC (15,2);

BEGIN
 SELECT SUM(MENGE) FROM LAGERBUCHUNG
  WHERE  ArtOID = :AOID 
  INTO :ZUB;

  IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;

  BESTAND = ZUB;
SUSPEND;
END
==============================================================================
P_BESTANDBLOCK                                                                                          1a:3804 
==============================================================================
RDB$PROCEDURE_SOURCE:  
      DECLARE VARIABLE ZUB NUMERIC (15,2);  BEGIN SELECT SUM(MENGE) FROM LAGERBUCHUNG  WHERE  ArtOID = :AOID AND LAGEROID in (Select OID from Lagerorte where Art = 'B')  

 INTO :ZUB; IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;    BESTAND = ZUB; SUSPEND; END
==============================================================================
P_BESTANDMINDEST                                                                                         1a:ef4 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  DECLARE VARIABLE ZUB NUMERIC (15,2);  DECLARE VARIABLE MINDEST NUMERIC (15,2);  BEGIN  SELECT SUM(MENGE) FROM LAGERBUCHUNG  WHERE  ArtOID = :AOID AND LAGEROID < 1100  INTO :ZUB;  IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;  SELECT COALESCE(MINDESTBESTANDNEU, 0) FROM ARTIKEL  WHERE  OID = :AOID INTO MINDEST;  BESTAND = ZUB - MINDEST;  SUSPEND; END
==============================================================================
P_BESTANDNACH                                                                                           1a:2eb1 
==============================================================================
RDB$PROCEDURE_SOURCE:  
        DECLARE VARIABLE ZUB NUMERIC (15,2);  BEGIN SELECT SUM(MENGE) FROM LAGERBUCHUNG    WHERE  ArtOID = :AOID AND  LAGEROID in ( select oid from lagerorte where lower(Art) = 'na' )   INTO :ZUB;    IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;    BESTAND = ZUB;   SUSPEND;  END
==============================================================================
P_BESTANDREP                                                                                            1a:2dc9 
==============================================================================
RDB$PROCEDURE_SOURCE:  
        DECLARE VARIABLE ZUB NUMERIC (15,2);  BEGIN SELECT SUM(MENGE) FROM LAGERBUCHUNG    WHERE  ArtOID = :AOID AND  LAGEROID in ( select oid from lagerorte where lower(Art) = 'r' )   INTO :ZUB;    IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;    BESTAND = ZUB;   SUSPEND;  END
==============================================================================
P_BESTANDSCHROTT                                                                                        1a:255f 
==============================================================================
RDB$PROCEDURE_SOURCE:  
       DECLARE VARIABLE ZUB NUMERIC (15,2);  BEGIN SELECT SUM(MENGE) FROM LAGERBUCHUNG    WHERE  ArtOID = :AOID AND LAGEROID in ( 1054, 2012, 2014, 2015, 3011, 3012 )  INTO :ZUB;    IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;    BESTAND = ZUB;   SUSPEND;  END
==============================================================================
P_BESTANDSPERR                                                                                           1a:d12 
==============================================================================
RDB$PROCEDURE_SOURCE:  
 DECLARE VARIABLE ZUB NUMERIC (15,2);  BEGIN  SELECT SUM(MENGE) FROM LAGERBUCHUNG  WHERE  ArtOID = :AOID AND (LAGEROID BETWEEN 1100 AND 1199)  INTO :ZUB; IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB; BESTAND = ZUB; SUSPEND; END
==============================================================================
P_BESTANDSPERR2                                                                                         1a:1585 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  DECLARE VARIABLE ZUB NUMERIC (15,2);  BEGIN  SELECT SUM(MENGE) FROM LAGERBUCHUNG  WHERE  ArtOID = :AOID AND (LAGEROID=1200)  INTO :ZUB; IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB; BESTAND = ZUB; SUSPEND; END
==============================================================================
P_BESTANDV                                                                                              1a:4070 
==============================================================================
RDB$PROCEDURE_SOURCE:  
      DECLARE VARIABLE ZUB NUMERIC (15,2);  DECLARE VARIABLE SCHROTT NUMERIC (15,2);  BEGIN SELECT SUM(MENGE) FROM LAGERBUCHUNG  WHERE  ArtOID = :AOID AND ( LAGEROID IN (SELECT OID from Lagerorte where coalesce(art, '0' ) <> 'S' )  OR LAGEROID = 0 )  INTO :ZUB;   IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;    BESTAND = ZUB; SUSPEND;  END
==============================================================================
P_BESTANDVNEW                                                                                           1a:157e 
==============================================================================
RDB$PROCEDURE_SOURCE:  
           DECLARE VARIABLE ZUB NUMERIC (15,2);  DECLARE VARIABLE SCHROTT NUMERIC (15,2); 

 BEGIN SELECT SUM(MENGE) FROM LAGERBUCHUNG  WHERE  ArtOID = :AOID AND LAGEROID IN 

 (SELECT OID from Lagerorte where coalesce(art, '0') <> 'S') INTO :ZUB;   IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB; 

 BESTAND = ZUB; SUSPEND;  END
==============================================================================
P_BESTAND_MINDESTKONT                                                                                    1a:870 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  DECLARE VARIABLE ZUB NUMERIC (15,4);  DECLARE VARIABLE MINDEST NUMERIC (15,4);  DECLARE VARIABLE KONT NUMERIC (15,4);  BEGIN  SELECT SUM(MENGE) FROM LAGERBUCHUNG  WHERE  ArtOID = :AOID AND LAGEROID < 1100  INTO :ZUB;  IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;  SELECT COALESCE(MINDESTBESTANDNEU, 0) FROM ARTIKEL  WHERE  OID = :AOID INTO MINDEST;  SELECT COALESCE(SUM(COALESCE(MINDEST,0)), 0) FROM ARTIKELKUNDE  WHERE  ARTOID = :AOID AND ABLAUF >= :ADATUM INTO KONT;  BESTAND = ZUB - MINDEST - KONT;  SUSPEND; END
==============================================================================

RDB$PROCEDURE_NAME                                                                            RDB$PROCEDURE_SOURCE 
=============================================================================== ==================== 
P_BESTELLPOS                                                                                             1a:3c9 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   BEGIN  for select B.OID,  B.NAME1, B.Belegdatum, B.Nummer, B.ADRNR, B.ADROID, P.OID, P.SOID, P.STCK, P.Preiseinheit,  P.PreisPreiseinheit, P.EPREIS, P.RABATT, P.ARTNR, P.EINHEIT, P.GPREIS, P.ORGPREIS, P.ORGEK, P.ARTOID, P.GELIEFERT,  P.BESTELLNR, P.Gebucht, P.Liefertermin, P.Lieferterminsoll, P.AbTermin  from Belegpos P, Beleg B  where P.SOID = B.OID and not Artoid is null and B.Belegart = 105 into  :OID, :NAME1, :Belegdatum, :Nummer, :ADRNR, :ADROID, :POID, :SOID, :STCK, :Preiseinheit, :PreisPreiseinheit, :EPREIS, :RABATT, :ARTNR, :EINHEIT, :GPREIS, :ORGPREIS, :ORGEK, :ARTOID, :GELIEFERT, :BESTELLNR, :Gebucht,  :Lieferterminpos, :Lieferterminsoll, :AbTermin Do suspend; END
==============================================================================
P_BESTELLPOSOID                                                                                          1a:fe3 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   BEGIN  for select B.OID,  B.NAME1, B.Belegdatum, B.Nummer, B.ADRNR, B.ADROID, P.OID, P.SOID, P.STCK, P.Preiseinheit,  P.PreisPreiseinheit, P.EPREIS, P.RABATT, P.ARTNR, P.EINHEIT, P.GPREIS, P.ORGPREIS, P.ORGEK, P.ARTOID, P.GELIEFERT,  P.BESTELLNR, P.Gebucht, P.Liefertermin, P.Lieferterminsoll, P.AbTermin  from Belegpos P, Beleg B  where P.SOID = B.OID and not Artoid is null and B.Belegart = 105 and P.ARTOID = :AOID  and Lieferterminsoll >= :DATUM1 and Lieferterminsoll <= :DATUM2 into  :OID, :NAME1, :Belegdatum, :Nummer, :ADRNR, :ADROID, :POID, :SOID, :STCK, :Preiseinheit, :PreisPreiseinheit, :EPREIS, :RABATT, :ARTNR, :EINHEIT, :GPREIS, :ORGPREIS, :ORGEK, :ARTOID, :GELIEFERT, :BESTELLNR, :Gebucht,  :Lieferterminpos, :Lieferterminsoll, :AbTermin Do suspend; END
==============================================================================
P_BESTELLT                                                                                               1a:3c4 
==============================================================================
RDB$PROCEDURE_SOURCE:  
                        

DECLARE VARIABLE ZUB NUMERIC (15,2);

BEGIN
 SELECT SUM(STCK) FROM Beleg B, Belegpos P
  WHERE  P.ArtOID = :AOID 
   AND B.OID = P.SOID 
   AND B.Belegart = 105
   AND B.Abgeschlossen ='F' 
   and ( (P.Gebucht is NULL) or (P.Gebucht = 'F') )
  INTO :ZUB;

  IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;

  BESTELLT = ZUB;
SUSPEND;
END
==============================================================================
P_BESTELLTABTERMIN                                                                                       1a:68a 
==============================================================================
RDB$PROCEDURE_SOURCE:  
      BEGIN select sum(coalesce(stck,0))  from Belegpos P, Beleg B  where B.Abgeschlossen = 'F' and B.OID = P.SOID and B.Belegart = 105  and P.ArtOID = :AOID and   (coalesce(P.Gebucht, 'F') = 'F' )    and P.ABTERMIN <= :ADATEBIS  into :BESTELLT; SUSPEND; END
==============================================================================
P_BESTELLTKWJAHR                                                                                         1a:1e7 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  

BEGIN

 select sum(stck)  from Belegpos P, Beleg B
    where B.Abgeschlossen = 'F' and B.OID = P.SOID and B.Belegart = 105
    and ArtOID = :AOID and (P.Gebucht is NULL or P.Gebucht = 'F' )
    and ABtermin >= :ADATEVON and ABTermin <= :ADATEBIS
  into :BESTELLT;
SUSPEND;
END
==============================================================================
P_BESTELLTKWJAHRSOLL                                                                                     1a:1f0 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   

BEGIN

 select sum(stck)  from Belegpos P, Beleg B
    where B.Abgeschlossen = 'F' and B.OID = P.SOID and B.Belegart = 105
    and ArtOID = :AOID and (P.Gebucht is NULL or P.Gebucht = 'F' )
    and ( ABtermin IS NULL ) AND Lieferterminsoll>= :ADATEVON and 
    Lieferterminsoll <= :ADATEBIS
  into :BESTELLT;
SUSPEND;
END
==============================================================================
P_BESTELLTSOLLTERMIN                                                                                     1a:59a 
==============================================================================
RDB$PROCEDURE_SOURCE:  
      BEGIN select sum(coalesce(stck,0))  from Belegpos P, Beleg B  where B.Abgeschlossen = 'F' and B.OID = P.SOID and B.Belegart = 105  and P.ArtOID = :AOID and   (coalesce(P.Gebucht, 'F') = 'F' )    and P.LIEFERTERMINSOLL<= :ADATEBIS  into :BESTELLT; SUSPEND; END
==============================================================================
P_BESTELLTVONBISNOPREIS                                                                                  1a:68d 
==============================================================================
RDB$PROCEDURE_SOURCE:  
        
  BEGIN 
   select sum(coalesce(stck,0))  from Belegpos P, Beleg B  where B.Abgeschlossen = 'F' and B.OID = P.SOID      and B.Belegart = 105  and P.ArtOID = :AOID and B.Belegdatum <= :ADATEBIS and
    B.Belegdatum >= :ADATEVON  and P.Epreis = 0 into :BESTELLT; SUSPEND; END
==============================================================================
P_BEWEGUNGIN                                                                                            1a:20b4 
==============================================================================
RDB$PROCEDURE_SOURCE:  
    BEGIN   select count(*) from LAGERBUCHUNG where not ( bemerkung like '%ventur%' )   and Artoid = :AOID and Datum between :DATUMAB and :DATUMBIS into :ANZAHL;  SUSPEND; END
==============================================================================
P_BGBAUMNRARTIKEL                                                                                       1a:13a1 
==============================================================================
RDB$PROCEDURE_SOURCE:  
           BEGIN

   BEGIN

     FOR

     Select OID, NUMMER, 0, ARTOID, NUMMER, 0, '', EKNETTO, 0 from

       Stuecklisten where OID =  :ASTOID ORDER by eknetto INTO

        :ASTAMMOID, :ASTAMMNR,:ASUBOID,:AARTOID, :ANUMMER, :AANZAHL, :AARTNR, :AEKNETTO, :AZEILEOID

       DO

     BEGIN

       FOR Select A.SOID, :ASTAMMNR, A.ASOID, A.ARTOID, S.NUMMER,A.ANZAHL,

       A.ARTNR, A.EKNETTO, A.OID  from Stuecklistenartikel A, Stuecklisten S

         where S.OID = A.SOID and A.ARTOID > 0 and   A.SOID = :ASTOID Order by eknetto

       Into :ASTAMMOID, :ASTAMMNR, :ASUBOID, :AARTOID, :ANUMMER, :AANZAHL, :AARTNR, :AEKNETTO, :AZEILEOID DO

       BEGIN

       SUSPEND;

       IF ((ASUBOID >0 ) AND (ASUBOID <> ASTOID)) THEN

       BEGIN

         FOR Select :ASTAMMOID, :ASTAMMNR, :ASUBOID, AARTOID, ANUMMER, AANZAHL,

           AARTNR, AEKNETTO, AZEILEOID from P_BGBaumNRARTIKEL(:ASUBOID) Order by Aeknetto

              into :ASTAMMOID, :ASTAMMNR, :ASUBOID, :AARTOID, :ANUMMER, :AANZAHL, :AARTNR, AEKNETTO, :AZEILEOID DO

          SUSPEND;

        END

      END

     END

     END

END
==============================================================================
P_BGBAUMNRARTIKELALL                                                                                    1a:148e 
==============================================================================
RDB$PROCEDURE_SOURCE:  
        BEGIN
  BEGIN
    FOR
      Select OID, NUMMER, 0, ARTOID, NUMMER, 0, '', 0 from Stuecklisten
        INTO :ASTAMMOID, :ASTAMMNR, :ASUBOID, :AARTOID, :ANUMMER, :AANZAHL, :AARTNR, :AZEILEOID DO
   BEGIN
     SUSPEND;
       FOR Select A.SOID, :ASTAMMNR, A.ASOID, A.ARTOID, S.NUMMER, A.ANZAHL, A.ARTNR, A.OID from Stuecklistenartikel A,
         STUECKLISTEN S where   S.OID = :ASTAMMOID  and A.SOID =  S.OID
                   Into :ASTAMMOID, :ASTAMMNR,:ASUBOID, :AARTOID, :ANUMMER,:AANZAHL,:AARTNR,:AZEILEOID  DO
         BEGIN
           SUSPEND;
             IF ((ASUBOID >0 ) AND (ASUBOID <> ASTAMMOID)) THEN
             BEGIN
               FOR Select :ASTAMMOID,:ASTAMMNR, :ASUBOID, AARTOID, ANUMMER, AANZAHL, AARTNR, AZEILEOID from
               P_BGBaumNRARTIKEL(:ASUBOID)
                 into :ASTAMMOID, :ASTAMMNR, :ASUBOID, :AARTOID, :ANUMMER, :AANZAHL,:AARTNR, :AZEILEOID DO
                 SUSPEND;
           END
         END
      END
   END
END
==============================================================================
P_BGBAUMNUMMER                                                                                          1a:12b3 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   BEGIN

   BEGIN
     FOR
     Select OID, 0, ARTOID, NUMMER from 
Stuecklisten where OID = :ASTOID INTO 
:ASTAMMOID, :ASUBOID, :AARTOID, 
:ANUMMER DO
     BEGIN
      SUSPEND;
      FOR Select SOID, ASOID, ARTOID, 
NUMMER
        from Stuecklistenartikel A, Stuecklisten S 
where S.OID = A.SOID and A.SOID = :ASTOID 
and coalesce(ASOID, 0)> 0
       Into :ASTAMMOID, :ASUBOID, :AARTOID, 
:ANUMMER DO
       BEGIN
        SUSPEND;
       IF ((ASUBOID >0 ) AND (ASUBOID <> 
ASTOID)) THEN
       BEGIN
         FOR Select * from P_BGBaumNUMMER
(:ASUBOID) into :ASTAMMOID, :ASUBOID, 
:AARTOID, :ANUMMER DO
         SUSPEND;
       END
      END
     END
     END
END
==============================================================================
P_BGBAUMNUMMERALL                                                                                       1a:139d 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN
  BEGIN
    FOR
      Select OID, 0, ARTOID, NUMMER from 
Stuecklisten 
        INTO :ASTAMMOID, :ASUBOID, 
:AARTOID, :ANUMMER DO
   BEGIN
     SUSPEND;
       FOR Select SOID, ASOID, ARTOID, 
S.NUMMER
            from Stuecklistenartikel, STUECKLISTEN 
S where 
                 SOID = :ASTAMMOID and SOID = 
S.OID and coalesce(ASOID, 0)> 0
                   Into :ASTAMMOID, :ASUBOID, 
:AARTOID, :ANUMMER DO
         BEGIN
           SUSPEND;
             IF ((ASUBOID >0 ) AND (ASUBOID <> 
ASTAMMOID)) THEN
             BEGIN
               FOR Select * from 
P_BGBaumNUMMER(:ASUBOID) 
                 into :ASTAMMOID, :ASUBOID, 
:AARTOID, :ANUMMER DO 
                 SUSPEND;
           END
         END
      END
   END
END
==============================================================================
P_CLEARSPACE                                                                                             1a:d1a 
==============================================================================
RDB$PROCEDURE_SOURCE:  
          DECLARE VARIABLE I Integer; DECLARE VARIABLE RESTVALUE VARCHAR(200); BEGIN RESTVALUE = :AVALUE; I = POSITION(" " in :RESTVALUE); ANOSPACE = ""; WHILE  (I > 0) DO   BEGIN ANOSPACE = ANOSPACE || LEFT(RESTVALUE, I-1); RESTVALUE = RIGHT(RESTVALUE, CHAR_LENGTH(RESTVALUE) - I);     I = POSITION(" " in :RESTVALUE); END  ANOSPACE = ANOSPACE || RIGHT(RESTVALUE, CHAR_LENGTH(RESTVALUE) - I);   SUSPEND; END  

==============================================================================
P_COUNTBESTELLTVONBISNOPREIS                                                                             1a:690 
==============================================================================
RDB$PROCEDURE_SOURCE:  
        
  BEGIN 
   select count(*)  from Belegpos P, Beleg B  where B.Abgeschlossen = 'F' and B.OID = P.SOID      
and B.Belegart = 105  and P.ArtOID = :AOID and B.Belegdatum <= :ADATEBIS and
    B.Belegdatum >= :ADATEVON  and P.Epreis = 0 into :BESTELLT; SUSPEND; END
==============================================================================
P_COUNTGELIEFERTVONBIS                                                                                   1a:693 
==============================================================================
RDB$PROCEDURE_SOURCE:  
        
  BEGIN 
   select count(*)  from Belegpos P, Beleg B  where B.Abgeschlossen = 'F' and B.OID = P.SOID   
   and B.Belegart = 105  and P.ArtOID = :AOID and B.Belegdatum <= :ADATEBIS and
    B.Belegdatum >= :ADATEVON  into :BESTELLT; SUSPEND; END
==============================================================================
P_CPMENGEBSBYPROD                                                                                       1a:166a 
==============================================================================
RDB$PROCEDURE_SOURCE:  
 BEGIN
 select sum(Menge) from prodzeitenschritt where PRODID = :APRODID
  and ARTID = :AART AND coalesce(SCHRITTBEZEICHNUNG, 'LS') = 'BS' INTO :MENGE;
SUSPEND;
END
==============================================================================
P_CPMENGEBYPROD                                                                                         1a:1491 
==============================================================================
RDB$PROCEDURE_SOURCE:  
BEGIN
 select sum(Menge) from prodzeitenschritt where PRODID = :APRODID
  and ARTID = :AART INTO :MENGE;
SUSPEND;
END
==============================================================================
P_CPMENGELSBYPROD                                                                                       1a:166e 
==============================================================================
RDB$PROCEDURE_SOURCE:  
 BEGIN
 select sum(Menge) from prodzeitenschritt where PRODID = :APRODID
  and ARTID = :AART AND coalesce(SCHRITTBEZEICHNUNG, 'LS') = 'LS' INTO :MENGE;
SUSPEND;
END
==============================================================================
P_CPMENGENIOBSBYPROD                                                                                    1a:1672 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN
 select sum(Fehler) from prodzeitenschritt where PRODID = :APRODID
  and ARTID = :AART AND coalesce(SCHRITTBEZEICHNUNG, 'LS') = 'BS' INTO :MENGE;
SUSPEND;
END
==============================================================================

RDB$PROCEDURE_NAME                                                                            RDB$PROCEDURE_SOURCE 
=============================================================================== ==================== 
P_CPMENGENIOBYPROD                                                                                      1a:1581 
==============================================================================
RDB$PROCEDURE_SOURCE:  
 BEGIN
 select sum(Fehler) from prodzeitenschritt where PRODID = :APRODID
  and ARTID = :AART INTO :MENGE;
SUSPEND;
END
==============================================================================
P_CPMENGENIOLSBYPROD                                                                                    1a:1676 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN
 select sum(Fehler) from prodzeitenschritt where PRODID = :APRODID
  and ARTID = :AART AND coalesce(SCHRITTBEZEICHNUNG, 'LS') = 'LS' INTO :MENGE;
SUSPEND;
END
==============================================================================
P_DATESELECT                                                                                             1a:d16 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   DECLARE VARIABLE TAG varchar(2); DECLARE VARIABLE Monat varchar(2);  BEGIN   TAG = extract(DAY from AValue);  IF (TAG < 10) THEN BEGIN TAG = '0' || TAG; END  MONAT = extract(MONTH from AValue); IF (MONAT < 10) then  BEGIN MONAT = '0' || MONAT; END  ADATE = :TAG || '.' || :MONAT || '.'  || extract(YEAR from AValue); SUSPEND; END
==============================================================================
P_EINS                                                                                                    1a:f8 
==============================================================================
RDB$PROCEDURE_SOURCE:  
                          

DECLARE VARIABLE TVALUE NUMERIC(15,6);
BEGIN
  IF ( (:AVALUE IS NULL) OR (:AVALUE = 0 ) ) THEN TVALUE = 1; ELSE TVALUE = :AVALUE;
  
  NVALUE = TVALUE;
SUSPEND;
END
==============================================================================
P_ERLOESKONTO                                                                                            1a:1e4 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN  SELECT NAME FROM KONTEN WHERE NUMMER = :AOID INTO :KONTO;  SUSPEND; END
==============================================================================
P_FERTIGUNGKWJAHR                                                                                        1a:86a 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN  select sum(Menge-coalesce(Fertig,0)) from Produktion P, Artikel A where  A.StueckOID = P.Artoid and A.OID = :AOID and P.STATUS <> -1   AND P.BEGINNDATUM >= :ADATEVON and  P.BEGINNDATUM <= :ADATEBIS  into INPRODUKTION;SUSPEND; END
==============================================================================
P_GELIEFERT                                                                                              1a:3c1 
==============================================================================
RDB$PROCEDURE_SOURCE:  
                        

DECLARE VARIABLE ZUB NUMERIC (15,2);

BEGIN
 SELECT SUM(GELIEFERT) FROM Beleg B, Belegpos P
  WHERE  P.ArtOID = :AOID 
   AND B.OID = P.SOID 
   AND B.Belegart = 105
   AND B.Abgeschlossen ='F' 
   and ( (P.Gebucht is NULL) or (P.Gebucht = 'F') )
  INTO :ZUB;

  IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;

  GELIEFERT = ZUB;
SUSPEND;
END
==============================================================================
P_GELIEFERTVONBIS                                                                                        1a:696 
==============================================================================
RDB$PROCEDURE_SOURCE:  
        
  BEGIN 
   select sum(coalesce(geliefert,0))  from Belegpos P, Beleg B  where B.Abgeschlossen = 'F' and B.OID = P.SOID      and B.Belegart = 105  and P.ArtOID = :AOID and B.Belegdatum <= :ADATEBIS and
    B.Belegdatum >= :ADATEVON  into :BESTELLT; SUSPEND; END
==============================================================================
P_GELIEFERTVT                                                                                            1a:e04 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  DECLARE VARIABLE ZUB NUMERIC (15,2);  BEGIN  SELECT SUM(coalesce(P.STCK, 0)) FROM Beleg B, Belegpos P WHERE  P.ArtOID = :ARTOID AND B.OID = P.SOID AND B.Belegart = :BELEGART  AND P.REFOID = :APOSOID INTO :ZUB;  IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB; GELIEFERT = ZUB; SUSPEND; END
==============================================================================
P_GPREISBESTELLTVONBIS                                                                                   1a:778 
==============================================================================
RDB$PROCEDURE_SOURCE:  
         
  BEGIN 
   select sum(GPreis)  from Belegpos P, Beleg B  where B.Abgeschlossen = 'F' and B.OID = P.SOID      
and B.Belegart = 105  and P.ArtOID = :AOID and B.Belegdatum <= :ADATEBIS and
    B.Belegdatum >= :ADATEVON into :BESTELLT; SUSPEND; END
==============================================================================
P_ISBAUGRUPPE                                                                                            1a:95b 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  DECLARE VARIABLE SID INTEGER; BEGIN  SELECT STUECKOID FROM ARTIKEL WHERE OID = :AOID INTO :SID;  ISBG = 'F'; IF (:SID > 0) then ISBG = 'T'; SUSPEND; END
==============================================================================
P_ISBG                                                                                                   1a:d1e 
==============================================================================
RDB$PROCEDURE_SOURCE:  
 DECLARE VARIABLE BGOID INTEGER;  BEGIN SELECT Stueckoid FROM Artikel WHERE OID = :AArtOID INTO :BGOID;   IF ((:BGOID IS NULL) or (:BGOID < 1)) THEN isBG = 'F' ; ELSE isBG = 'T';  SUSPEND; END
==============================================================================
P_KM                                                                                                      1a:ef 
==============================================================================
RDB$PROCEDURE_SOURCE:  
 BEGIN 
  SELECT SUM(KMENDE) - SUM(KMANFANG) FROM FUHRPARKKM WHERE (DATUM >= :AVON OR DATUM <= :ABIS) AND SOID = :AOID INTO KM; 
 IF (KM IS NULL) THEN KM = 0; ELSE KM = CAST((KM * 100) AS INTEGER) / 100; SUSPEND; END
==============================================================================
P_KOSTENSTELLE                                                                                            1a:fe 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN  SELECT NAME FROM KONTEN WHERE NUMMER = :AOID INTO :KOSTENSTELLE;  SUSPEND; END
==============================================================================
P_KUNDARTIKELALL                                                                                        1a:10d4 
==============================================================================
RDB$PROCEDURE_SOURCE:  
 BEGIN  
   
    FOR select distinct StueckOID from Artikel A, 
Belegpos P, Beleg B 
     where B.OID = P.Soid and P.Artoid = A.oid 
and A.StueckOID > 0 
      and B.Belegart = 101 and B.adroid = 
:AADROID INTO :ASOID DO
    SUSPEND;

    
END
==============================================================================
P_LEK                                                                                                    1a:2ce 
==============================================================================
RDB$PROCEDURE_SOURCE:  
                                          

DECLARE VARIABLE MAXOID INTEGER;
DECLARE VARIABLE LEKRP NUMERIC(15, 6);
DECLARE VARIABLE LEKAB NUMERIC(15, 6);
      
BEGIN
 SELECT MAX(BELEGPOS.OID) FROM BELEGPOS,BELEG
  WHERE BELEG.BELEGART = 105
  AND BELEGPOS.SOID = BELEG.OID
  AND not STCK is NULL
  AND not GPreis is NULL
  AND GPREIS > 0
  AND BELEGPOS.ARTOID = :AOID
  INTO :MAXOID;
 BEGIN 
  SELECT GPREIS / STCK FROM BELEGPOS 
  WHERE OID = :MAXOID
  INTO :LEKAB; 
  WHEN SQLCODE -802 DO
    LEK = 0;
 END
 BEGIN
  SELECT Lieferpreis / Geliefert FROM BELEGPOS 
  WHERE OID = :MAXOID
  INTO :LEKRP; 
  WHEN SQLCODE -802 DO
    LEKRP = 0;
 END 
   IF (:LEKRP >= 0) THEN LEK = :LEKRP;  
 
  IF (:LEKAB IS NULL) THEN LEK = 0; ELSE LEK = :LEKAB;  
 
  SUSPEND;
END
==============================================================================
P_LEKAB                                                                                                  1a:86e 
==============================================================================
RDB$PROCEDURE_SOURCE:  
 BEGIN  SELECT first 1 case when P.ABTermin is NULL then  P.LieferterminSoll   else   P.ABTermin  end,  p.Epreis, B.Adroid, B.name1, P.Stck, B.AdrNR  from belegpos P, Beleg B where artoid = :AOID  and B.Belegart = 105 and B.OID = P.Soid and coalesce(p.geliefert, 0) = 0  and coalesce(p.Stck, 0) > 0  order by  case when ABTermin is NULL then   LieferterminSoll  else   ABTermin  end Desc    INTO :DATUM, :LEK, :ADROID, :LIEFERANT, :MENGE, :ADRNR; SUSPEND; END 

==============================================================================
P_LEKDATUM                                                                                               1a:4b8 
==============================================================================
RDB$PROCEDURE_SOURCE:  
                                           

DECLARE VARIABLE MAXOID INTEGER;
DECLARE VARIABLE DATUMAB DATE;
DECLARE VARIABLE DATUMLS DATE;
      
BEGIN
 SELECT MAX(BELEGPOS.OID) FROM BELEGPOS,BELEG
  WHERE BELEG.BELEGART = 105
  AND BELEGPOS.SOID = BELEG.OID
  AND not STCK is NULL
  AND not GPreis is NULL
  AND GPREIS > 0
  AND BELEGPOS.ARTOID = :AOID
  INTO :MAXOID;
 BEGIN 
  SELECT ABTERMIN FROM BELEGPOS 
  WHERE OID = :MAXOID
  INTO :DATUMAB; 
  WHEN SQLCODE -802 DO
   DATUMAB = '01.01.1900'; 
 END

 BEGIN
  SELECT Lieferterminsoll FROM BELEGPOS 
  WHERE OID = :MAXOID
  INTO :DATUMLS; 
  WHEN SQLCODE -802 DO
    DATUMLS = '01.01.1900';
 END 
   IF (:DATUMAB > '01.01.1900' ) THEN LEKDATUM = :DATUMAB;  
 
  SUSPEND;
END
==============================================================================
P_LEKLIEFER                                                                                              1a:95f 
==============================================================================
RDB$PROCEDURE_SOURCE:  
     DECLARE VARIABLE MAXOID INTEGER;  DECLARE VARIABLE LEKRP NUMERIC(15, 6);  DECLARE VARIABLE LEKAB NUMERIC(15, 6);  
  BEGIN  
    SELECT max(Belegpos.oid) FROM BELEGPOS,BELEG  WHERE BELEG.BELEGART = 105  AND BELEGPOS.SOID = BELEG.OID  
  and coalesce(Geliefert, 0) > 0  AND lieferpreis > 0  AND BELEGPOS.ARTOID = :AOID  AND BELEG.ADROID = :ALIEFER 
  and belegpos.liefertermin =
    (SELECT MAX(Belegpos.liefertermin) FROM BELEGPOS,BELEG  WHERE BELEG.BELEGART = 105  AND BELEGPOS.SOID = BELEG.OID 
      and coalesce(Geliefert, 0) > 0  AND lieferpreis > 0  AND BELEGPOS.ARTOID = :AOID  AND BELEG.ADROID = :ALIEFER)
    INTO :MAXOID; 

   
    BEGIN  SELECT Lieferpreis / Geliefert FROM BELEGPOS  WHERE OID = :MAXOID  INTO :LEKRP;  WHEN SQLCODE -802 DO    
    LEKRP = 0; END  IF (:LEKRP >= 0) THEN LEK = :LEKRP;   SUSPEND; END
==============================================================================
P_LEKRP                                                                                                 1a:4d7f 
==============================================================================
RDB$PROCEDURE_SOURCE:  
     DECLARE VARIABLE DATUMLS D_Date_Leer;  DECLARE VARIABLE LEKRPM NUMERIC(15, 6); DECLARE VARIABLE MAXOID INTEGER;  BEGIN     BEGIN       SELECT FIRST 1 MAX(BELEGPOS.Liefertermin), BELEGPOS.OID FROM BELEGPOS,BELEG     WHERE BELEG.BELEGART = 105      AND BELEGPOS.SOID = BELEG.OID      AND not STCK is NULL       AND not GPreis is NULL       AND GPREIS > 0      AND BELEG.OID >= 51637     AND BELEGPOS.ARTOID = :AOID     AND NOT LIEFERTERMIN is NULL     AND coalesce(rgnrlief, '') <> ''    group by OID      ORDER by  1 DESC     INTO :DATUMLS, :MAXOID;   END  BEGIN   SELECT Lieferpreis / Geliefert FROM BELEGPOS    WHERE OID = :MAXOID   INTO :LEKRPM;   WHEN SQLCODE -802 DO       LEKRP = 0;  END    IF (:LEKRPM >= 0) THEN LEKRP = :LEKRPM;   SUSPEND;  END 

==============================================================================

RDB$PROCEDURE_NAME                                                                            RDB$PROCEDURE_SOURCE 
=============================================================================== ==================== 
P_LEKRPALL                                                                                              1a:59a4 
==============================================================================
RDB$PROCEDURE_SOURCE:  
     BEGIN   select first 1 P.Liefertermin, p.Lieferpreis/(coalesce(p.Ufaktor, 1)*P.geliefert), B.Adroid, B.name1, p.Geliefert, B.AdrNr          from belegpos P, Beleg B where artoid = :AOID and B.Belegart = 105 and B.OID = P.Soid  and coalesce(geliefert, 0) > 0         and not RGNRLIEF is NULL order by Liefertermin desc    INTO :DATUM, :LEK, :ADROID, :LIEFERANT, :MENGE, :ADRNR;      SUSPEND;    END 

==============================================================================
P_LETZTEBEWEGUNG                                                                                         1a:e0d 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   DECLARE VARIABLE DATUMAB DATE; DECLARE VARIABLE DATUMLS DATE; DECLARE VARIABLE DATUMP DATE;
  BEGIN
    SELECT MAX(DATUM) FROM LAGERBUCHUNG WHERE ARTOID = :AOID INTO :DATUMLS;
    SELECT MAX(BELEGDATUM) FROM BELEG B, BELEGPOS P WHERE B.OID=P.SOID  AND B.BELEGART = 105 AND P.ARTOID = :AOID INTO :DATUMAB;
    SELECT MAX(BEGINNDATUM) FROM PRODUKTION P, PRODARTIKEL A WHERE P.OID  = A.SOID AND A.ARTOID = :AOID INTO :DATUMP;
    IF (:DATUMAB > :DATUMLS ) THEN LASTDATUM = :DATUMAB; ELSE LASTDATUM = :DATUMLS;
    IF (:DATUMP > LASTDATUM ) THEN LASTDATUM = :DATUMP;
    IF (:DATUMAB > :DATUMLS ) THEN LASTDATUM = :DATUMAB; ELSE LASTDATUM = :DATUMLS;
       SUSPEND;
    END
==============================================================================
P_LETZTEBEWEGUNGNOINV                                                                                   1a:175c 
==============================================================================
RDB$PROCEDURE_SOURCE:  
    DECLARE VARIABLE DATUMAB DATE; DECLARE VARIABLE DATUMLS DATE; DECLARE VARIABLE DATUMP DATE;  BEGIN SELECT MAX(DATUM) FROM LAGERBUCHUNG WHERE (ARTOID = :AOID and not bemerkung like '%Inventur%' ) INTO :DATUMLS;   SELECT MAX(BELEGDATUM) FROM BELEG B, BELEGPOS P WHERE B.OID=P.SOID  AND B.BELEGART = 105 AND P.ARTOID = :AOID INTO :DATUMAB;   SELECT MAX(BEGINNDATUM) FROM PRODUKTION P, PRODARTIKEL A WHERE P.OID  = A.SOID AND A.ARTOID = :AOID INTO :DATUMP;   IF (:DATUMAB > :DATUMLS ) THEN LASTDATUM = :DATUMAB; ELSE LASTDATUM = :DATUMLS;  IF (:DATUMP > LASTDATUM ) THEN LASTDATUM = :DATUMP;   IF (:DATUMAB > :DATUMLS ) THEN LASTDATUM = :DATUMAB; ELSE LASTDATUM = :DATUMLS;     SUSPEND;  END
==============================================================================
P_MAHASQUALIOIDONE                                                                                      1a:1589 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN
 FOR Select OID from StueckPersQuali where PersID = :AUSERID 
   AND SOID = :ASTUECKID and Quali = 'T'
  INTO :OID

DO
SUSPEND;
END
==============================================================================
P_MAXBZ                                                                                                 1a:59a2 
==============================================================================
RDB$PROCEDURE_SOURCE:  
    BEGIN
  select first 1 max(coalesce(Lieferzeit,0)), Lieferant, gueltig_bis,
   (((EKBrutto/coalesce(Preiseinheit, 1))*((100 - Rabatt)/100))/coalesce(Ufaktor,1)) as EKBrutto,
   Mengevon, Mengebis from Artikelpreise where soid = :AOID
  group by 2,3,4,5,6
  order by 1 desc, 3
 INTO :MAXBZ, :ADROID, :GUELTIG, :PREIS, 
:Mengevon, :MengeBis; SUSPEND; END
 

==============================================================================
P_MEK                                                                                                    1a:2d4 
==============================================================================
RDB$PROCEDURE_SOURCE:  
                                 
      
BEGIN
 BEGIN 
   SELECT SUM(GPREIS) / SUM(STCK) FROM BELEGPOS,BELEG
     WHERE BELEG.BELEGART = 105
     AND BELEGPOS.SOID = BELEG.OID
     AND not GPREIS is NULL
     AND GPREIS > 0
     AND not STCK is NULL
     AND ARTOID = :AOID
     INTO :MEK;
   WHEN SQLCODE -802 Do MEK = 0;
  END  
  IF (:MEK IS NULL) THEN MEK = 0; ELSE MEK = CAST((:MEK * 10000) AS INTEGER) / 10000;
SUSPEND;
END
==============================================================================
P_MEKLAST                                                                                                1a:a50 
==============================================================================
RDB$PROCEDURE_SOURCE:  
 BEGIN  Select SUM(PREIS)/:AROWS from P_PREISLAST(:AOID, :AROWS) into :PREIS; SUSPEND; END
==============================================================================
P_MEKLASTN                                                                                              1a:167a 
==============================================================================
RDB$PROCEDURE_SOURCE:  
 BEGIN  BEGIN with lastmek as (select first 10  p.oid, GPreis, stck, GPreis/stck as EPreis from beleg b, belegpos p    where b.belegart = 105 and b.oid = p.soid and p.artoid = :AOID     AND not GPREIS is NULL AND GPREIS > 0  AND not STCK is NULL order by p.oid desc  )  select (sum(Epreis))/count(*) from lastmek INTO : MEK;  WHEN SQLCODE -802 Do MEK = 0; END  IF (:MEK IS NULL) THEN MEK = 0; ELSE MEK = CAST((:MEK * 10000) AS INTEGER) / 10000;  SUSPEND; END  

==============================================================================
P_MEKLIEFER                                                                                              1a:a45 
==============================================================================
RDB$PROCEDURE_SOURCE:  
    BEGIN BEGIN SELECT SUM(Lieferpreis) / SUM(Geliefert) FROM BELEGPOS,BELEG 
  WHERE BELEG.BELEGART = 105 AND BELEGPOS.SOID = BELEG.OID  
  AND BELEG.ADROID = :AADROID AND not GPREIS is NULL AND Lieferpreis > 0 
  AND not Geliefert is NULL AND ARTOID = :AOID INTO :MEK;  WHEN SQLCODE -802 Do MEK = 0; END  IF (:MEK IS NULL) THEN MEK = 0; ELSE MEK = CAST((:MEK * 10000) AS INTEGER) / 10000; SUSPEND; END
==============================================================================
P_MEKRP                                                                                                  1a:957 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN BEGIN SELECT SUM(Lieferpreis) / SUM(Geliefert) FROM BELEGPOS,BELEG  WHERE BELEG.BELEGART = 105  AND BELEG.OID >= 51637   AND BELEGPOS.SOID = BELEG.OID  AND not Lieferpreis is NULL   AND Lieferpreis > 0   AND coalesce(Geliefert, 0) > 0   AND ARTOID = :AOID   INTO :MEK;   WHEN SQLCODE -802 Do MEK = 0;  END  IF (:MEK IS NULL) THEN MEK = 0; ELSE MEK = CAST((:MEK * 10000) AS INTEGER) / 10000;  SUSPEND;  END
==============================================================================
P_MEKRPN                                                                                                1a:1758 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   BEGIN  BEGIN   with lastmek as  (select first 10  p.oid, Lieferpreis/Geliefert as EPreis from beleg b, belegpos p   where b.belegart = 105 and b.oid = p.soid and p.artoid = :AOID     AND not Lieferpreis is NULL   AND Lieferpreis > 0       AND coalesce(Geliefert, 0) > 0      AND not STCK is NULL   order by p.oid desc  )  select (sum(Epreis))/count(*) from lastmek INTO : MEK;  WHEN SQLCODE -802 Do MEK = 0; END   IF (:MEK IS NULL) THEN MEK = 0; ELSE MEK = CAST((:MEK * 10000) AS INTEGER) / 10000;  SUSPEND;  END  

==============================================================================
P_MINBZ                                                                                                 1a:59a9 
==============================================================================
RDB$PROCEDURE_SOURCE:  
    BEGIN
  select first 1 max(coalesce(Lieferzeit,0)), Lieferant, gueltig_bis,
   (((EKBrutto/coalesce(Preiseinheit, 1))*((100 - Rabatt)/100))/coalesce(Ufaktor,1)) as EKBrutto,
   Mengevon, Mengebis from Artikelpreise where
soid = :AOID
  group by 2,3,4,5,6
  order by 1, 3
 INTO :MAXBZ, :ADROID, :GUELTIG, :PREIS, 
:Mengevon, :MengeBis; SUSPEND; END
 

==============================================================================
P_MINPREIS                                                                                              1a:12af 
==============================================================================
RDB$PROCEDURE_SOURCE:  
    BEGIN
  select min(((EKBrutto/coalesce(Preiseinheit, 1))*((100 - Rabatt)/100))/coalesce(Ufaktor,1)) as
    EKBrutto, Lieferant, gueltig_bis, Lieferzeit, Mengevon, Mengebis from
Artikelpreise where soid = :AOID
  group by 2,3,4,5,6
order by 1, 3

 INTO :PREIS, :ADROID, :GUELTIG, :MAXBZ,
:Mengevon, :MengeBis; SUSPEND; END
==============================================================================
P_NULL                                                                                                    1a:f5 
==============================================================================
RDB$PROCEDURE_SOURCE:  
                       

DECLARE VARIABLE TVALUE NUMERIC(15,6);
BEGIN
  IF (:AVALUE IS NULL) THEN TVALUE = 0; ELSE TVALUE = :AVALUE;
  NVALUE = TVALUE;
SUSPEND;
END
==============================================================================
P_OFFENAUFTRAG                                                                                           1a:e08 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   BEGIN   Select sum(Coalesce(Stck, 0) - coalesce(Geliefert, 0)) from Belegpos P, Beleg B where p.Artoid = :AArtOID and  b.OID = p.SOID and B.Belegart in (72, 10030) and  p.Liefertermin <= :ADatum  and p.OID <> :AIgnore and B.abgeschlossen <> 'T'  INTO :Anzahl;  SUSPEND; END
==============================================================================
P_PREISLAST                                                                                              1a:963 
==============================================================================
RDB$PROCEDURE_SOURCE:  
 BEGIN  FOR Select GPREIS/STCK FROM BELEGPOS,BELEG WHERE BELEG.BELEGART = 105 AND ARTOID = :AOID  AND BELEGPOS.SOID = BELEG.OID AND not GPREIS is NULL AND GPREIS > 0 AND not STCK is NULL  order by BELEG.OID DESC ROWS 1 to :AROWS INTO :PREIS DO SUSPEND; END
==============================================================================
P_PRODBEDARFKW                                                                                           1a:3be 
==============================================================================
RDB$PROCEDURE_SOURCE:  
    

BEGIN
  select sum(Sollmenge - Buchmenge) 
from Produktion P, Prodartikel M
where 
  P.OID = M.Soid AND 
  Artoid = :AOID
    And (Sollmenge - Buchmenge) > 0 and 
     (Status <> -1 or Status is NULL and Einheitmenge > 0)
    And (Kw = :KW and Jahr = :Jahr)
  into :BEDARF;
SUSPEND;
END
==============================================================================
P_PRODBEREIT1KW                                                                                          1a:5a3 
==============================================================================
RDB$PROCEDURE_SOURCE:  
     BEGIN      Select sum(Prodmenge*prodAnzahl*Artmenge) from T_Bereit1     where ArtOID = :AOID And KW = :KW and Jahr = :Jahr        into :BEDARF;    SUSPEND;    END
==============================================================================
P_PRODBEREIT2KW                                                                                          1a:5a0 
==============================================================================
RDB$PROCEDURE_SOURCE:  
     BEGIN      Select sum(Prodmenge*prodAnzahl*Artmenge) from T_Bereit2     where ArtOID = :AOID And KW = :KW and Jahr = :Jahr        into :BEDARF;    SUSPEND;    END
==============================================================================
P_PRODBEREIT3KW                                                                                          1a:59d 
==============================================================================
RDB$PROCEDURE_SOURCE:  
     BEGIN      Select sum(Prodmenge*prodAnzahl*Artmenge) from T_Bereit3     where ArtOID = :AOID And KW = :KW and Jahr = :Jahr        into :BEDARF;    SUSPEND;    END
==============================================================================

RDB$PROCEDURE_NAME                                                                            RDB$PROCEDURE_SOURCE 
=============================================================================== ==================== 
P_PRODBEREITKW                                                                                           1a:3c7 
==============================================================================
RDB$PROCEDURE_SOURCE:  
    

BEGIN
  Select sum(menge*Anzahl) 
   
from ProduktionBereit P, Stuecklistenartikel M, Stuecklisten S

where 
  ( P.Status is null or P.Status > -1 ) 
  AND S.OID = M.Soid and S.OID = P.ArtOID 
  AND M.ArtOID = :AOID And (KW = :KW and Jahr = :Jahr)
  into :BEDARF;
SUSPEND;
END
==============================================================================
P_PRODBEREITNACHKW0                                                                                      1a:ef8 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   BEGIN   Select sum(Prodmenge*Anzahl) from V_Bereitmaterial   where ArtOID = :AOID And ((KW >= :KW and Jahr = :Jahr)   or ( Jahr > :Jahr))  into :BEDARF; SUSPEND;  END
==============================================================================
P_PRODBEREITNACHKW1                                                                                      1a:efc 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   BEGIN  Select sum(Prodmenge*ProdAnzahl*Anzahl) from  V_BereitmaterialSUB  where ArtOID = :AOID And ((KW >= :KW and Jahr = :Jahr)   or (Jahr >:Jahr))  into :BEDARF;  SUSPEND;  END
==============================================================================
P_PRODBEREITNACHKW2                                                                                      1a:5a9 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   BEGIN  Select sum(Prodmenge*ProdAnzahl*Artmenge) from T_BEREIT2    where ArtOID = :AOID And ((KW >= :KW and Jahr = :Jahr)   or (Jahr >:Jahr))  into :BEDARF;  SUSPEND;  END
==============================================================================
P_PRODBEREITNACHKW3                                                                                      1a:5a6 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   BEGIN  Select sum(Prodmenge*ProdAnzahl*Artmenge) from T_BEREIT3    where ArtOID = :AOID And ((KW >= :KW and Jahr = :Jahr)   or (Jahr >:Jahr))  into :BEDARF;  SUSPEND;  END
==============================================================================
P_PRODBEREITVORKW0                                                                                       1a:f04 
==============================================================================
RDB$PROCEDURE_SOURCE:  
BEGIN
  Select sum(Prodmenge*Anzahl) from V_Bereitmaterial 
    where ArtOID = :AOID And (KW < :KW and Jahr <= :Jahr)
    into :BEDARF;
SUSPEND;
END
==============================================================================
P_PRODBEREITVORKW1                                                                                       1a:f00 
==============================================================================
RDB$PROCEDURE_SOURCE:  
BEGIN
  Select sum(Prodmenge*ProdAnzahl) from V_BereitmaterialSUB 
    where ArtOID = :AOID And (KW < :KW and Jahr <= :Jahr)
    into :BEDARF;
SUSPEND;
END
==============================================================================
P_PRODBEREITVORKW2                                                                                       1a:4b2 
==============================================================================
RDB$PROCEDURE_SOURCE:  
               BEGIN              Select sum(Prodmenge*ProdAnzahl*Artmenge) from T_BEREIT2  where ArtOID = :AOID And (KW < :KW and Jahr <= :Jahr)    into :BEDARF; SUSPEND;     END
==============================================================================
P_PRODBEREITVORKW3                                                                                       1a:5ac 
==============================================================================
RDB$PROCEDURE_SOURCE:  
               BEGIN              Select sum(Prodmenge*ProdAnzahl*Artmenge) from T_BEREIT3  where ArtOID = :AOID And (KW < :KW and Jahr <= :Jahr)    into :BEDARF; SUSPEND;     END
==============================================================================
P_PRODZEITENAUFTRAG                                                                                      1a:c26 
==============================================================================
RDB$PROCEDURE_SOURCE:  
        BEGIN  select  sum(b.RUESTZEIT*:AFaktor)/3600, sum(b.Zeit * Anzahl)*:AFaktor/3600  from prodartikel A, produktion P, Artikel Ar  left join Bauformen b on (B.OID = Ar.Bauform and B.Typ = 'S') where  P.OID = A.Soid and Ar.OID = A.Artoid and P.AUFTRAGOID = :AAUFTRAG INTO :SMTR, SMTP; select  sum(b.RUESTZEIT*:AFaktor)/3600, sum(b.Zeit * Anzahl)*:AFaktor/3600 from prodartikel A, produktion P, Artikel Ar left join Bauformen b on (B.OID = Ar.Bauform and B.Typ = 'P') where  P.OID = A.Soid and Ar.OID = A.Artoid and P.AUFTRAGOID = :AAUFTRAG INTO :THTR, THTP; select  sum(b.RUESTZEIT*:AFaktor)/3600, sum(b.Zeit * Anzahl)*:AFaktor/3600 from prodartikel A, produktion P, Artikel Ar left join Bauformen b on (B.OID = Ar.Bauform and B.Typ = 'K') where  P.OID = A.Soid and Ar.OID = A.Artoid and P.AUFTRAGOID = :AAUFTRAG INTO :KabelR, KabelP; SUSPEND; END
==============================================================================
P_PRODZEITENDAY                                                                                          1a:b34 
==============================================================================
RDB$PROCEDURE_SOURCE:  
        BEGIN  select  sum(b.RUESTZEIT*:AFaktor)/3600, sum(b.Zeit * Anzahl)*:AFaktor/3600  from prodartikel A, produktion P, Artikel Ar  left join Bauformen b on (B.OID = Ar.Bauform and B.Typ = 'S') where  P.OID = A.Soid and Ar.OID = A.Artoid and P.BEGINNDATUM = :ADatum INTO :SMTR, SMTP; select  sum(b.RUESTZEIT*:AFaktor)/3600, sum(b.Zeit * Anzahl)*:AFaktor/3600 from prodartikel A, produktion P, Artikel Ar left join Bauformen b on (B.OID = Ar.Bauform and B.Typ = 'P') where  P.OID = A.Soid and Ar.OID = A.Artoid and P.BEGINNDATUM = :ADatum INTO :THTR, THTP; select  sum(b.RUESTZEIT*:AFaktor)/3600, sum(b.Zeit * Anzahl)*:AFaktor/3600 from prodartikel A, produktion P, Artikel Ar left join Bauformen b on (B.OID = Ar.Bauform and B.Typ = 'K') where  P.OID = A.Soid and Ar.OID = A.Artoid and P.BEGINNDATUM = :ADatum INTO :KabelR, KabelP; SUSPEND; END
==============================================================================
P_PRODZEITENENDDAY                                                                                       1a:b38 
==============================================================================
RDB$PROCEDURE_SOURCE:  
        BEGIN  select  sum(b.RUESTZEIT*:AFaktor)/3600, sum(b.Zeit * Anzahl)*:AFaktor/3600  from prodartikel A, produktion P, Artikel Ar  left join Bauformen b on (B.OID = Ar.Bauform and B.Typ = 'S') where  P.OID = A.Soid and Ar.OID = A.Artoid and P.ENDEDATUM = :ADatum INTO :SMTR, SMTP; select  sum(b.RUESTZEIT*:AFaktor)/3600, sum(b.Zeit * Anzahl)*:AFaktor/3600 from prodartikel A, produktion P, Artikel Ar left join Bauformen b on (B.OID = Ar.Bauform and B.Typ = 'P') where  P.OID = A.Soid and Ar.OID = A.Artoid and P.ENDEDATUM = :ADatum INTO :THTR, THTP; select  sum(b.RUESTZEIT*:AFaktor)/3600, sum(b.Zeit * Anzahl)*:AFaktor/3600 from prodartikel A, produktion P, Artikel Ar left join Bauformen b on (B.OID = Ar.Bauform and B.Typ = 'K') where  P.OID = A.Soid and Ar.OID = A.Artoid and P.ENDEDATUM = :ADatum INTO :KabelR, KabelP; SUSPEND; END
==============================================================================
P_PRODZEITENONE                                                                                          1a:a4b 
==============================================================================
RDB$PROCEDURE_SOURCE:  
        BEGIN  select  sum(b.RUESTZEIT*:AFaktor)/3600, sum(b.Zeit * Sollmenge)*:AFaktor/3600  from prodartikel A, produktion P, Artikel Ar  left join Bauformen b on (B.OID = Ar.Bauform and B.Typ = 'S') where  P.OID = A.Soid and Ar.OID = A.Artoid and P.OID = :AProdID INTO :SMTR, SMTP; select  sum(b.RUESTZEIT*:AFaktor)/3600, sum(b.Zeit * Sollmenge)*:AFaktor/3600 from prodartikel A, produktion P, Artikel Ar left join Bauformen b on (B.OID = Ar.Bauform and B.Typ = 'P') where  P.OID = A.Soid and Ar.OID = A.Artoid and P.OID = :AProdID INTO :THTR, THTP; select  sum(b.RUESTZEIT*:AFaktor)/3600, sum(b.Zeit * Sollmenge)*:AFaktor/3600 from prodartikel A, produktion P, Artikel Ar left join Bauformen b on (B.OID = Ar.Bauform and B.Typ = 'K') where  P.OID = A.Soid and Ar.OID = A.Artoid and P.OID = :AProdID INTO :KabelR, KabelP; SUSPEND; END
==============================================================================
P_RECHNUNGFAELLIG                                                                                          1a:a 
==============================================================================
RDB$PROCEDURE_SOURCE:  
               
BEGIN
  SELECT faellig FROM zkondi
   WHERE OID = :AOID
   INTO :TAGE;
  
  IF (:TAGE IS NULL) THEN TAGE = 0; ELSE TAGE = :TAGE;
  SUSPEND;
END
==============================================================================
P_SA01                                                                                                   1a:77b 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN UPDATE STUECKLISTENARTIKEL S SET ARTNR = (SELECT ARTNR from ARTIKEL where OID = :AArtOID)  WHERE S.OID = :ASOID; END
==============================================================================
P_SA02                                                                                                   1a:77e 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN UPDATE STUECKLISTENARTIKEL S SET Identnr1 = (SELECT Identnr1 from ARTIKEL where OID = :AArtOID)  WHERE S.OID = :ASOID; END
==============================================================================
P_SA03                                                                                                   1a:781 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN UPDATE STUECKLISTENARTIKEL S SET Identnr2 = (SELECT Identnr2 from ARTIKEL where OID = :AArtOID)  WHERE S.OID = :ASOID; END
==============================================================================
P_SA04                                                                                                   1a:784 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN UPDATE STUECKLISTENARTIKEL S SET Identnr3 = (SELECT Identnr3 from ARTIKEL where OID = :AArtOID)  WHERE S.OID = :ASOID; END
==============================================================================
P_SA05                                                                                                   1a:787 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN UPDATE STUECKLISTENARTIKEL S SET Identnr4 = (SELECT Identnr4 from ARTIKEL where OID = :AArtOID)  WHERE S.OID = :ASOID; END
==============================================================================
P_SA06                                                                                                   1a:78a 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN UPDATE STUECKLISTENARTIKEL S SET Identnr5 = (SELECT Identnr5 from ARTIKEL where OID = :AArtOID)  WHERE S.OID = :ASOID; END
==============================================================================

RDB$PROCEDURE_NAME                                                                            RDB$PROCEDURE_SOURCE 
=============================================================================== ==================== 
P_SA07                                                                                                   1a:78d 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN UPDATE STUECKLISTENARTIKEL S SET Bezeichnung1 = (SELECT Bezeichnung1 from ARTIKEL where OID = :AArtOID)  WHERE S.OID = :ASOID; END
==============================================================================
P_SA08                                                                                                   1a:790 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN UPDATE STUECKLISTENARTIKEL S SET Bezeichnung2 = (SELECT Bezeichnung2 from ARTIKEL where OID = :AArtOID)  WHERE S.OID = :ASOID; END
==============================================================================
P_SA09                                                                                                   1a:867 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN UPDATE STUECKLISTENARTIKEL S SET Einheit = (SELECT Einheit from ARTIKEL where OID = :AArtOID)  WHERE S.OID = :ASOID; END
==============================================================================
P_SA10                                                                                                   1a:1f4 
==============================================================================
RDB$PROCEDURE_SOURCE:  
  BEGIN UPDATE STUECKLISTENARTIKEL S SET ASOID = (SELECT STUECKOID from ARTIKEL where OID = :AArtOID)  WHERE S.OID = :ASOID; END
==============================================================================
P_SPARTE                                                                                                 1a:1ea 
==============================================================================
RDB$PROCEDURE_SOURCE:  
 BEGIN  SELECT NAME FROM SPARTEN WHERE OID = :AOID INTO :NAME;  SUSPEND; END
==============================================================================
P_STARTIKEL                                                                                             1a:10cf 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   BEGIN   BEGIN    FOR Select SOID, ASOID, ARTOID, Artnr, (Anzahl*:AMenge) from Stuecklistenartikel where SOID = :ASTOID   Into :ASOID, :AASOID, :AARTOID, :AArtnr, :Menge DO    BEGIN   SUSPEND;      IF ((AASOID >0 ) AND (AASOID <> ASOID)) THEN    BEGIN        FOR Select * from P_STARTIKEL(:AASOID, :MENGE) into :ASOID, :AASOID, :AARTOID, :AArtnr, :Menge DO        SUSPEND; END  END END END
==============================================================================
P_STARTIKELKUNDE                                                                                        1a:11c0 
==============================================================================
RDB$PROCEDURE_SOURCE:  
    DECLARE VARIABLE ADRSTID 
INTEGER;
    DECLARE VARIABLE ASSTID INTEGER;
  BEGIN
   IF (:AADROID < 0) THEN
   BEGIN
     FOR Select SOID, ASOID, ARTOID, Artnr
          from Stuecklistenartikel where SOID = 
:ASTOID
          Into :ASOID, :AASOID, :AARTOID, :AArtnr 
DO
            BEGIN
              SUSPEND;
               ASSTID = coalesce(AASOID, 0);
               IF ((ASSTID >0 ) AND (ASSTID <> 
ASOID)) THEN
               BEGIN
                 FOR Select * from 
P_STARTIKELKUNDE(-222, :ASSTID) into 
:ASOID, :AASOID, :AARTOID, :AArtnr DO
                 SUSPEND;
               END

            END
          SUSPEND;
   END

   IF (:AADROID > 0) THEN
   BEGIN
     FOR SELECT ASOID FROM 
P_KUNDARTIKELALL(:AADROID) into 
:ADRSTID DO
       BEGIN
          FOR Select SOID, ASOID, ARTOID, Artnr
            from Stuecklistenartikel where SOID = 
:ADRSTID
              Into :ASOID, :AASOID, :AARTOID, 
:AArtnr DO 
              BEGIN
              SUSPEND;
               ASSTID = coalesce(AASOID, 0);
               IF ((ASSTID >0 ) AND (ASSTID <> 
ASOID)) THEN
               BEGIN
                 FOR Select * from 
P_STARTIKELKUNDE(-222, :ASSTID) into 
:ASOID, :AASOID, :AARTOID, :AArtnr DO
                 SUSPEND;
               END
               
            END
            
            SUSPEND;
       END
       SUSPEND;
   END
END
==============================================================================
P_STATUS                                                                                                 1a:1ed 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   BEGIN  SELECT STATUS FROM BELEGSTATUS WHERE OID = :AOID INTO :STATUS;  SUSPEND; END
==============================================================================
P_STBEREIT                                                                                              1a:10d6 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   DECLARE Variable BArtoid Integer;  DECLARE Variable BMenge Integer; DECLARE Variable BBEGINN D_Date_Leer; BEGIN  BEGIN   FOR select ArtOID, Menge, Beginndatum from ProduktionBereit where coalesce(Status, 0) <> -1     into :BArtoid, :Bmenge, :Beginn Do BEGIN  FOR Select ASOID, AASOID, AARTOID, AArtnr, Menge from P_Startikel(:BArtOID, :BMenge)       Into :ASOID, :AASOID, :AARTOID, :AArtnr, :Menge Do SUSPEND; END END END
==============================================================================
P_TOPBOT                                                                                                 1a:ef0 
==============================================================================
RDB$PROCEDURE_SOURCE:  
   BEGIN  select cast(list(DISTINCT FARBNR, '/') as varchar(10)) from Stuecklistenartikel where artoid = :AARTOID  and soid = :ASTUECKOID Into TOPBOT;  SUSPEND; END
==============================================================================
P_VERFUEGBAR                                                                                               1a:7 
==============================================================================
RDB$PROCEDURE_SOURCE:  
                  

DECLARE VARIABLE ZUB NUMERIC (15,2);
DECLARE VARIABLE AB NUMERIC (15,2);
DECLARE VARIABLE AB2 NUMERIC (15,2);

BEGIN
 SELECT SUM(GELIEFERT) FROM BELEGPOS,BELEG
  WHERE (BELEG.BELEGART = 205
  OR BELEG.BELEGART = 405)
  AND BELEGPOS.SOID = BELEG.OID
  AND BELEGPOS.ARTOID = :AOID
  INTO :ZUB;

 SELECT SUM(STCK) FROM BELEGPOS,BELEG
  WHERE (BELEG.BELEGART = 203
  OR BELEG.BELEGART = 206 
  OR BELEG.BELEGART = 403)
  AND BELEGPOS.SOID = BELEG.OID
  AND ARTOID = :AOID
  INTO :AB;

 SELECT SUM(STCK) FROM BELEGPOS,BELEG
  WHERE (BELEG.BELEGART = 200
  OR BELEG.BELEGART = 300 
  OR BELEG.BELEGART = 400)
  AND BELEGPOS.SOID = BELEG.OID
  AND ARTOID = :AOID
  INTO :AB2;

  IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;

  IF (:AB IS NULL) THEN AB = 0; ELSE AB = :AB;

  IF (:AB2 IS NULL) THEN AB2 = 0; ELSE AB2 = :AB2;

  BESTAND = ZUB  - AB - AB2;
SUSPEND;
END
==============================================================================

