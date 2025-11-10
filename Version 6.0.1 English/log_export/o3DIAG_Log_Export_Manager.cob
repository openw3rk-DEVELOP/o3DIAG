      *------------------------------
      *o3DIAG Log Export Manager
      *------------------------------
      *Copyright (c) openw3rk INVENT
      *License: MIT-License
      *------------------------------
      *https://openw3rk.de
      *https://o3diag.openw3rk.de
      *https://o3diag.openw3rk.de/help/develop/cobol
      *-----------------------------------------------

       IDENTIFICATION DIVISION.
       PROGRAM-ID. O3DIAG-LOG-EXPORT-MANAGER.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUT-FILE ASSIGN TO DYNAMIC WS-FILE-IN
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT OUTPUT-FILE ASSIGN TO DYNAMIC WS-FILE-OUT
               ORGANIZATION IS LINE SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.
       FD  INPUT-FILE.
       01  INPUT-LINE PIC X(256).
       FD  OUTPUT-FILE.
       01  OUTPUT-LINE PIC X(256).

       WORKING-STORAGE SECTION.
       01  WS-FILE-IN       PIC X(256).
       01  WS-FILE-OUT      PIC X(256).
       01  EOF-FLAG         PIC X VALUE "N".

       PROCEDURE DIVISION.
       MAIN-LOGIC.
           ACCEPT WS-FILE-IN FROM ARGUMENT-VALUE
           ACCEPT WS-FILE-OUT FROM ARGUMENT-VALUE

           OPEN INPUT INPUT-FILE
           OPEN OUTPUT OUTPUT-FILE

           PERFORM UNTIL EOF-FLAG = "Y"
              READ INPUT-FILE
                 AT END MOVE "Y" TO EOF-FLAG
                 NOT AT END
                    MOVE INPUT-LINE TO OUTPUT-LINE
                    WRITE OUTPUT-LINE
              END-READ
           END-PERFORM

           MOVE SPACES TO OUTPUT-LINE
           WRITE OUTPUT-LINE
           MOVE "Created with o3DIAG Log Export Manager." TO OUTPUT-LINE
           WRITE OUTPUT-LINE

           CLOSE INPUT-FILE
           CLOSE OUTPUT-FILE
           STOP RUN.
