CREATE DATABASE IF NOT EXISTS evaluation_system;
USE evaluation_system;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS tbl_evaluation_details;
DROP TABLE IF EXISTS tbl_evaluation;
DROP TABLE IF EXISTS tbl_evaluation_questions;
DROP TABLE IF EXISTS tbl_teacher; 
DROP TABLE IF EXISTS tbl_student;
DROP TABLE IF EXISTS tbl_admin;

CREATE TABLE tbl_admin (
    a_id       INT          AUTO_INCREMENT PRIMARY KEY,
    a_username VARCHAR(50)  NOT NULL UNIQUE,
    a_password VARCHAR(255) NOT NULL 
);

CREATE TABLE tbl_teacher ( 
    t_id         INT          PRIMARY KEY AUTO_INCREMENT, 
    t_username   VARCHAR(50)  UNIQUE NOT NULL, 
    t_password   VARCHAR(255) NOT NULL, 
    t_email      VARCHAR(255) NOT NULL, 
    t_first_name VARCHAR(255) NOT NULL, 
    t_last_name  VARCHAR(255) NOT NULL, 
    t_course     VARCHAR(255) NOT NULL 
);

CREATE TABLE tbl_student (
    s_id          INT          PRIMARY KEY AUTO_INCREMENT,
    s_schoolID    VARCHAR(50)  NOT NULL UNIQUE,
    s_password    VARCHAR(255) NOT NULL, 
    s_email       VARCHAR(255) NOT NULL, 
    s_first_name  VARCHAR(255) NOT NULL,
    s_last_name   VARCHAR(255) NOT NULL,
    s_year_level  VARCHAR(50)  NOT NULL,
    s_status      ENUM('Pending', 'Approved') DEFAULT 'Pending'
);


CREATE TABLE tbl_evaluation_questions (
    q_id    INT          AUTO_INCREMENT PRIMARY KEY,
    q_text  TEXT         NOT NULL,
    q_order INT          NOT NULL UNIQUE
);

CREATE TABLE tbl_evaluation (
    e_id             INT          AUTO_INCREMENT PRIMARY KEY,
    s_schoolID       VARCHAR(50)  NOT NULL,
    t_id             INT          NOT NULL,
    e_remarks        TEXT,
    e_date_submitted DATETIME     DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_evaluation (s_schoolID, t_id),
    FOREIGN KEY (s_schoolID) REFERENCES tbl_student(s_schoolID) ON DELETE CASCADE,
    FOREIGN KEY (t_id) REFERENCES tbl_teacher(t_id) ON DELETE CASCADE
);

CREATE TABLE tbl_evaluation_details (
    ed_id  INT AUTO_INCREMENT PRIMARY KEY,
    e_id   INT NOT NULL,
    q_id   INT NOT NULL,
    ed_value TINYINT NOT NULL COMMENT 'Rating from 1 to 5',
    FOREIGN KEY (e_id) REFERENCES tbl_evaluation(e_id) ON DELETE CASCADE,
    FOREIGN KEY (q_id) REFERENCES tbl_evaluation_questions(q_id)
);

SET FOREIGN_KEY_CHECKS = 1;

INSERT INTO tbl_admin (a_username, a_password) VALUES
('admin', 'password'); 

INSERT INTO tbl_evaluation_questions (q_text, q_order) VALUES
('Subject matter knowledge and expertise.', 1),
('Clarity of explanations and organization of lessons.', 2),
('Fairness and helpfulness in providing feedback.', 3),
('Overall effectiveness as a teacher.', 4),
('Responsible for his/her mistakes.', 5);

INSERT INTO tbl_teacher (t_username, t_password, t_email, t_first_name, t_last_name, t_course) VALUES
('ching', 'ching', 'ching@scc.edu', 'Ching', 'Archival', 'Art Appreciation'),
('dalley', 'dalley', 'dalley@scc.edu', 'Dalley', 'Alterado', 'Economica, Taxation, and LAnd Reforms'),
('rose', 'rose', 'rose@scc.edu', 'Rose', 'Gamboa', 'Logic'),
('aries', 'aries', 'aries@scc.edu', 'Aries', 'Dajay', 'Information Management'),
('fil', 'fil', 'fil@scc.edu', 'Fil', 'Aripal', 'PC AD'),
('joseph', 'joseph', 'joseph@scc.edu', 'Joseph', 'Lanza', 'Principles of Accounting');